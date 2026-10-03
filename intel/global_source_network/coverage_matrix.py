# O-3D.5 -- Global Source Coverage Matrix (sections 3/4/37/38).
#
# A read-only audit, not a new Source Registry system (section 3: "불필요한 신규 Source 시스템을
# 만들지 않는다"). Reuses sources.json (the real collection config briefing.py already reads) for
# REGISTERED counts, and intel/documents.json + geography_inference.py's existing country
# inference for ACTIVE/observed counts. Never fabricates a count: a cell with no evidence stays
# blank (None), never 0-by-assumption vs 0-by-measurement conflated.
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
INTEL_DIR = HERE.parent
ROOT = INTEL_DIR.parent
OUT_PATH = HERE / "coverage_matrix_result.json"

sys.path.insert(0, str(INTEL_DIR / "geographic_evidence"))
import geography_inference as gi  # noqa: E402

CORE_REGIONS = ("KR", "US", "CN", "EU", "JP", "IN")

# section 4's row taxonomy, mapped onto field keywords already present in sources.json/documents
# (분야 -- an internal diagnostic grouping only, distinct from the 11-field Daily Taxonomy).
ROW_HINTS = (
    "정부", "입법", "규제기관", "법·제도", "개인정보", "저작권/IP", "공식 통계",
    "산업·경제", "노동", "연구·과학", "의료", "에너지·환경", "국방·안보",
    "교육·사회", "문화·예술", "미디어·콘텐츠", "AI 정책", "국제질서",
)


def _load_json(path, default):
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _sources_config():
    return _load_json(ROOT / "sources.json", {"sources": []})


def _documents():
    data = _load_json(INTEL_DIR / "documents.json", {})
    if isinstance(data, dict):
        return {k: v for k, v in data.items() if isinstance(v, dict)}
    return {d["document_id"]: d for d in data if isinstance(d, dict) and "document_id" in d}


def registered_sources_by_country():
    """Section 4 row 'REGISTERED': counts sources.json entries by country. KR/US are inferred
    from the existing category convention (news_ko/papers-ko => KR; the collector's only other
    convention is a flat news_global/papers bucket with no built-in country split, so those count
    toward a source's explicit `country_hint` when present, and stay UNCOUNTED (not zero) when
    absent -- never guessed from category alone for non-KR sources."""
    cfg = _sources_config()
    counts = {c: 0 for c in CORE_REGIONS}
    uncounted = 0
    for s in cfg.get("sources", []):
        hint = s.get("country_hint")
        if hint in counts:
            counts[hint] += 1
        elif s.get("category") in ("news_ko",):
            counts["KR"] += 1
        else:
            uncounted += 1  # honestly not attributable to one of the 6 core regions from config alone
    return {"by_country": counts, "uncounted": uncounted, "total_sources": len(cfg.get("sources", []))}


def active_sources_by_country(documents=None):
    """Section 4 row 'ACTIVE': distinct source_ids that appear at least once in the current
    documents.json corpus with a resolvable country (TLD rule or SOURCE_ID_COUNTRY registry).
    This is an OBSERVED-activity count, not a health-check result -- a source with 0 observed
    documents in the current window is NOT_SEEN, never silently treated as inactive/broken."""
    documents = documents if documents is not None else _documents()
    by_country = {c: set() for c in CORE_REGIONS}
    for doc in documents.values():
        country = doc.get("country")
        sid = doc.get("source_id")
        if not country:
            inferred = gi.infer_document_geography(doc)
            country = inferred["country"] if inferred else None
        if country in by_country and sid:
            by_country[country].add(sid)
    return {c: sorted(v) for c, v in by_country.items()}


def build_coverage_matrix():
    registered = registered_sources_by_country()
    active = active_sources_by_country()
    rows = {}
    for row in ROW_HINTS:
        # Section 4: blank cells stay blank (None) -- this corpus has no per-row(분야)x country
        # source tagging today, so every cell here is honestly None (NOT_AVAILABLE) rather than a
        # fabricated 0. Only the per-country REGISTERED/ACTIVE totals above are real counts.
        rows[row] = {c: None for c in CORE_REGIONS}
    return {
        "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "registered_by_country": registered["by_country"],
        "registered_uncounted": registered["uncounted"],
        "registered_total_sources": registered["total_sources"],
        "active_source_ids_by_country": active,
        "active_source_count_by_country": {c: len(v) for c, v in active.items()},
        "matrix_rows": rows,
        "matrix_row_note": (
            "분야 x 국가 세부 Coverage는 현재 데이터로 산출 불가 (NOT_AVAILABLE) -- "
            "가짜 Coverage를 표시하지 않기 위해 모든 셀을 비워둠 (section 4/39)."
        ),
    }


def main():
    result = build_coverage_matrix()
    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "registered_by_country": result["registered_by_country"],
        "active_source_count_by_country": result["active_source_count_by_country"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
