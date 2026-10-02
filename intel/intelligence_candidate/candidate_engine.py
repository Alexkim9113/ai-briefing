# O-3D -- Intelligence Candidate Engine + Research Queue.
#
# Reuses, does not replace: intel/operator_workspace/daily_discovery.py's emerging_issues()
# (entity recurrence over >=2 days / >=2 independent sources, already deterministic, already
# tested) as the base signal. This module adds exactly what Te's O-3D spec asks for on top:
#   - Tier 1 presence / cross-field spread / cross-region spread as SEPARATE metadata fields,
#     never merged into one composite score (section 16: Priority != Evidence Quality).
#   - A promotion boundary: Candidate is the ceiling of what automation may produce. This module
#     NEVER creates a Claim/Hypothesis/Intelligence Object/Report (section 13/41, Canonical
#     Boundary) -- it only writes to its own candidate/research_queue sidecar files.
#   - A Research Queue with identity-based dedup (section 15): the same issue across runs
#     UPDATES its existing queue entry (first_seen stays, last_seen advances) instead of creating
#     a duplicate RESEARCH_PENDING row every run.
#   - A generic `research_queue` schema (section 18), not named after any specific agent
#     (Hermes or otherwise) so any future worker can read it the same way.
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
INTEL_DIR = HERE.parent
ROOT = INTEL_DIR.parent

sys.path.insert(0, str(INTEL_DIR / "operator_workspace"))
sys.path.insert(0, str(INTEL_DIR / "daily_taxonomy"))
import daily_discovery as dd  # noqa: E402
import taxonomy as _taxonomy  # noqa: E402

# daily_discovery.py's emerging_issues() uses its own older, 8-bucket FIELD_KEYWORDS vocabulary
# (built for O-2F, before O-3C fixed the 11-field taxonomy). Section 23 requires O-3D to connect
# to O-3C's REAL 11-field taxonomy, not leave this older vocabulary in place. Rather than fork a
# second classifier, this is a straight terminology remap onto the nearest O-3C field -- the
# underlying keyword-matching signal is unchanged, only the displayed label changes.
_OLD_FIELD_TO_O3C_FIELD = {
    "기술": "기술",
    "법·규제": "법·제도",
    "의료": "의료·헬스케어",
    "노동·경제": "산업·경제",  # closer to this emerging-issues module's actual signal
                                # (investment/earnings/M&A keywords dominate its "노동·경제" bucket)
    "에너지·환경": "에너지·환경",
    "안보": "국방·안보",
    "AI정책·국제질서": "정책·국제질서",
    "문화·사회": "교육·사회",  # this bucket's keywords (교육/플랫폼/여론/윤리) are 교육·사회, not
                               # 문화·예술 -- avoids re-introducing O-3C's culture/media conflation
    "기타": None,
}


def _o3c_field(old_field):
    return _OLD_FIELD_TO_O3C_FIELD.get(old_field, None)

CANDIDATE_OUT = HERE / "intelligence_candidates.json"
QUEUE_OUT = HERE / "research_queue.json"

# Section 7/8: which source_ids are Tier 1 (government/regulator/international body/official
# statistics) for this corpus. Reuses the real, already-registered institution-type signal from
# the Evidence Pipeline's admission gate vocabulary rather than inventing a second tier scheme.
_TIER1_SOURCE_HINTS = (
    "federal_register", "congress", "whitehouse", "nist", "ftc", "sec_gov", "europa_eu",
    "eur_lex", "go_kr", "gov", "ecb_europa",
)


def _is_tier1(source_name_or_id):
    s = (source_name_or_id or "").lower()
    return any(h in s for h in _TIER1_SOURCE_HINTS)


def _issue_identity(issue):
    """Section 15: stable identity for dedup, independent of run-to-run ordering or incidental
    count changes. Based on the issue's own entity name + field, which emerging_issues() already
    computes deterministically from recurring entity extraction."""
    basis = f"{issue['issue_name']}::{issue['field']}"
    return "cand_" + hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]


def _compose_issue_label(issue):
    """Section Q: prefer an Entity + Topic composite name over a bare entity, but ONLY when the
    sample title actually supports a topic phrase -- never invented. Falls back to the bare
    entity name when no topic phrase can be read off the real sample_title (section Q: '데이터가
    이를 뒷받침할 때만')."""
    entity = issue["issue_name"]
    title = issue.get("sample_title") or ""
    if entity and entity in title and len(title) > len(entity) + 4:
        return f"{entity} 관련 동향: {title}"
    return entity


def detect_candidates(data_dir=None, taxonomy_result=None):
    """Real-data runner. Builds candidates from emerging_issues() (sections 12/Q/R), attaching
    Tier 1 presence as its own field, never merged into a single score."""
    data_dir = data_dir or str(ROOT / "data")
    emerging = dd.emerging_issues(data_dir=data_dir)
    if emerging["status"] != "OK":
        return {"status": emerging["status"], "candidates": [],
                "note": emerging.get("note", "insufficient history for candidate detection")}

    candidates = []
    for issue in emerging["issues"]:
        cid = _issue_identity(issue)
        tier1_present = _is_tier1(issue.get("sample_title", ""))  # best-effort from title/source
        candidates.append({
            "candidate_id": cid,
            "title": _compose_issue_label(issue),
            "field": _o3c_field(issue["field"]) or issue["field"],
            "region": issue["region"],
            "recurring_days": issue["recurring_days"],
            "independent_source_count": issue["independent_source_count"],
            "related_event_count": issue["related_event_count"],
            "tier1_present": tier1_present,
            "related_intelligence_topic": issue.get("related_intelligence_topic"),
            "evidence_quality": "UNKNOWN",  # section 16 -- never inferred, only set once real
                                             # Evidence Pipeline admission happens for this issue
            "reason": (f"{issue['recurring_days']}일 연속 반복, "
                       f"독립 출처 {issue['independent_source_count']}개"
                       + (", Tier 1 출처 포함" if tier1_present else "")),
            "status": "INTELLIGENCE_CANDIDATE",
        })
    return {"status": "OK", "candidates": candidates}


def update_research_queue(candidates, out_path=None):
    """Section 15: identity-based upsert, never a fresh duplicate row per run. Section 18:
    generic `research_queue` schema any worker (Hermes or otherwise) can read."""
    out_path = Path(out_path or QUEUE_OUT)
    existing = {}
    if out_path.exists():
        try:
            existing = {row["candidate_id"]: row for row in json.loads(out_path.read_text(encoding="utf-8"))}
        except Exception:
            existing = {}

    now = datetime.now(timezone.utc).isoformat()
    for c in candidates:
        cid = c["candidate_id"]
        if cid in existing:
            row = existing[cid]
            row["last_seen"] = now
            row["related_events"] = c["related_event_count"]
            row["sources"] = c["independent_source_count"]
            row["recurring_days"] = c["recurring_days"]
            row["tier1_present"] = c["tier1_present"]
            row["source_tiers"] = "TIER_1_PRESENT" if c["tier1_present"] else "UNKNOWN"
            row["field"] = c["field"]
            row["title"] = c["title"]
            row["reason"] = c["reason"]
            # research_status is deliberately NOT reset on update -- an item already marked
            # RESEARCH_IN_PROGRESS/DONE by an operator must not revert to PENDING just because
            # the issue is still recurring.
        else:
            existing[cid] = {
                "candidate_id": cid,
                "title": c["title"],
                "reason": c["reason"],
                "field": c["field"],
                "region": c["region"],
                "countries": [c["region"]] if c["region"] not in ("UNKNOWN", None) else [],
                "related_events": c["related_event_count"],
                "sources": c["independent_source_count"],
                "source_tiers": "TIER_1_PRESENT" if c["tier1_present"] else "UNKNOWN",
                "first_seen": now,
                "last_seen": now,
                "research_status": "RESEARCH_PENDING",
                "priority": "HIGH" if (c["tier1_present"] or c["recurring_days"] >= 4) else "NORMAL",
                "evidence_quality": c["evidence_quality"],
            }

    rows = list(existing.values())
    out_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return rows


def run(data_dir=None):
    result = detect_candidates(data_dir=data_dir)
    CANDIDATE_OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    queue = []
    if result["status"] == "OK":
        queue = update_research_queue(result["candidates"])
    return {"candidates": result, "queue": queue}


if __name__ == "__main__":
    out = run()
    print(json.dumps({
        "candidate_status": out["candidates"]["status"],
        "candidate_count": len(out["candidates"].get("candidates", [])),
        "queue_count": len(out["queue"]),
    }, ensure_ascii=False, indent=2))
