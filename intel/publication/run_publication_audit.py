#!/usr/bin/env python3
# Publication Gate Shadow Audit 실행기. intel/documents.json(기존 Phase 3-A 산출물, 읽기 전용) +
# data/*.json(원본, 읽기 전용)을 읽어 intel/publication/*.json을 만든다.
# site/, briefing.py Public Renderer, search.json은 이 스크립트 어디에서도 열지 않는다(21번).
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from publication_gate import decide_rights, build_public_payload, build_search_payload  # noqa: E402

INTEL_DIR = ROOT / "intel"
PUB_DIR = INTEL_DIR / "publication"
SECTIONS = ["news_ko", "news_global", "papers", "policy", "talks", "editor"]


def load_documents():
    return json.loads((INTEL_DIR / "documents.json").read_text(encoding="utf-8"))


def load_raw_items():
    """document_id(=기존 article id) -> 원본 item(mx.b/mx.p/detail 등 포함) 매핑.
    Phase 3-A의 intel/documents.json에는 rights 판단용 메타데이터만 있고 실제 본문 필드는
    없으므로, BEFORE/AFTER 비교를 위해 원본 data/*.json도 함께 읽는다(읽기 전용)."""
    by_id = {}
    for f in ROOT.glob("data/2026-*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for it in d.get("items", []):
            by_id[it["id"]] = it
    # 에디터 글도 원본 필드(body 대신 summary만 있음)가 필요하면 posts에서 보강
    posts_dir = ROOT / "editor" / "posts"
    if posts_dir.exists():
        for pf in posts_dir.glob("*.json"):
            try:
                p = json.loads(pf.read_text(encoding="utf-8"))
            except Exception:
                continue
            import hashlib
            did = hashlib.sha1(p["id"].encode()).hexdigest()
            by_id[did] = {"id": did, "source": "에디터", "summary": p.get("summary", ""),
                          "detail": p.get("body", ""), "cover": p.get("cover", "")}
    return by_id


def run():
    documents = load_documents()
    raw_items = load_raw_items()

    audits, public_payloads, search_payloads = [], {}, {}
    rights_dist = Counter()
    section_stats = defaultdict(lambda: Counter())
    summary_blocked = 0
    point_blocked = 0
    image_blocked = 0
    before_after_samples = []

    for did, doc in documents.items():
        raw = raw_items.get(did)
        decision = decide_rights(doc)
        rights_dist[decision["rights_mode"]] += 1

        cat = doc.get("category") or "unknown"
        st = section_stats[cat]
        st["documents"] += 1
        st[decision["rights_mode"]] += 1
        if not decision.get("_external_image_allowed", decision["rights_mode"] in
                            ("METAXIS_ORIGINAL", "LICENSED", "OPEN_LICENSE", "PUBLIC_DOMAIN")):
            st["external_image_blocked"] += 1
            image_blocked += 1
        if "summary" in decision["blocked_fields"]:
            st["summary_blocked"] += 1
            summary_blocked += 1
        if "mx.p" in decision["blocked_fields"]:
            point_blocked += 1

        payload = build_public_payload(doc, raw, decision)
        search_payload = build_search_payload(doc, decision)
        public_payloads[did] = payload
        search_payloads[did] = search_payload

        audits.append({
            "document_id": did, "document_type": doc.get("document_type"),
            "source": raw.get("source") if raw else doc.get("source_id"),
            "rights_mode": decision["rights_mode"],
            "allowed_fields": decision["allowed_fields"],
            "blocked_fields": decision["blocked_fields"],
            "reason": decision["reason"],
        })

    # BEFORE/AFTER 실제 사례 10건: 각 주요 섹션에서 mx(b/p) 있는 실제 문서를 우선 고른다
    picked = 0
    for cat in ["news_ko", "news_global", "papers", "policy"]:
        for did, doc in documents.items():
            if picked >= 10:
                break
            if doc.get("category") != cat:
                continue
            raw = raw_items.get(did)
            if not raw or not raw.get("mx"):
                continue
            decision = decide_rights(doc)
            before_after_samples.append({
                "document_id": did,
                "before_current_public_card": {
                    "title": doc.get("title"),
                    "quick_brief_mx_b": raw.get("mx", {}).get("b"),
                    "metaxis_point_mx_p": raw.get("mx", {}).get("p"),
                    "thumb": raw.get("thumb") or None,
                    "source": raw.get("source"),
                },
                "after_publication_gate_card": public_payloads.get(did),
                "rights_mode": decision["rights_mode"],
            })
            picked += 1
        if picked >= 10:
            break

    total_docs = len(documents)
    metrics = {
        "total_documents": total_docs,
        "rights_mode_distribution": dict(rights_dist),
        "summary_blocked_count": summary_blocked,
        "metaxis_point_blocked_count": point_blocked,
        "external_image_blocked_count": image_blocked,
        "metaxis_original_count": rights_dist.get("METAXIS_ORIGINAL", 0),
        "link_only_count": rights_dist.get("LINK_ONLY", 0) + rights_dist.get("GOV_OFFICIAL", 0)
                            + rights_dist.get("MANUAL_REVIEW", 0),
        "information_density_note": (
            f"{total_docs}건 중 {summary_blocked}건({round(100*summary_blocked/total_docs, 1) if total_docs else 0}%)이 "
            "Quick Brief(summary) 없이 제목+링크만 남게 됨"
        ),
        "gemini_calls_added": 0, "claude_calls_added": 0, "external_api_calls": 0,
    }
    section_readiness = {cat: dict(st) for cat, st in section_stats.items()}

    PUB_DIR.mkdir(exist_ok=True)
    (PUB_DIR / "public_payload.json").write_text(
        json.dumps(public_payloads, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    (PUB_DIR / "public_search_payload.json").write_text(
        json.dumps(search_payloads, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    (PUB_DIR / "publication_audit.json").write_text(
        json.dumps(audits, ensure_ascii=False, indent=1), encoding="utf-8")
    (PUB_DIR / "publication_readiness.json").write_text(
        json.dumps(section_readiness, ensure_ascii=False, indent=1), encoding="utf-8")
    (PUB_DIR / "before_after_samples.json").write_text(
        json.dumps(before_after_samples, ensure_ascii=False, indent=1), encoding="utf-8")
    (PUB_DIR / "publication_metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")
    return metrics, section_readiness, before_after_samples


if __name__ == "__main__":
    m, sec, samples = run()
    print(json.dumps(m, ensure_ascii=False, indent=1))
    print(json.dumps(sec, ensure_ascii=False, indent=1))
    print(f"before/after samples: {len(samples)}")
