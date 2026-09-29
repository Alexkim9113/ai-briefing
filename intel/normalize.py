#!/usr/bin/env python3
# Phase 3-A Pilot 실행기. data/*.json(기존, 읽기 전용) → intel/*.json(신규, Shadow Store).
# 기존 파이프라인·briefing.py·site/는 전혀 쓰지 않고 함수만 가져다 쓴다(import만, 파일 변경 없음).
# 이 스크립트는 daily.yml에서 호출되지 않는다 — Public Site와 완전히 분리된 별도 실행.
import json
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import briefing  # noqa: E402  (기존 코드, 함수만 재사용 — 이 스크립트에서 절대 수정하지 않음)

from source_service import normalize_sources, _domain_from_url  # noqa: E402
from document_service import to_document  # noqa: E402
from fact_service import make_fact_candidate  # noqa: E402
from event_service import cluster_events  # noqa: E402
from storage.json_store import JsonStore  # noqa: E402

INTEL_DIR = ROOT / "intel"
PILOT_CATEGORIES = ["news_ko", "news_global", "papers", "policy"]
PILOT_PER_CAT = 125  # 4개 분야 x 125 ≈ 500건 샘플(운영자 지시 11: 300~500건)


def load_recent_items(days=7):
    files = sorted(ROOT.glob("data/2026-*.json"), reverse=True)[:days]
    items = []
    for f in files:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for it in d.get("items", []):
            items.append(it)
    return items


def sample_items(items):
    by_cat = defaultdict(list)
    for it in items:
        by_cat[it.get("category")].append(it)
    sample = []
    for c in PILOT_CATEGORIES:
        pool = sorted(by_cat.get(c, []), key=lambda x: x.get("published") or "", reverse=True)
        sample += pool[:PILOT_PER_CAT]
    return sample


def normalized_topic_of(item):
    try:
        name, _ = briefing.topic_of(item)
        return name
    except Exception:
        return None


def normalized_entities_of(item):
    try:
        return set(briefing.mx_actors(item))
    except Exception:
        return set()


def run():
    t0 = time.time()
    now_iso = datetime.now(timezone.utc).isoformat()
    all_items = load_recent_items()
    sample = sample_items(all_items)
    dup_ids = Counter(it["id"] for it in sample)
    sample = list({it["id"]: it for it in sample}.values())  # 같은 id가 여러 날짜 파일에 걸쳐 있으면 하나만

    source_store, doc_store, fact_store, event_store = (
        JsonStore(INTEL_DIR / "sources.json"), JsonStore(INTEL_DIR / "documents.json"),
        JsonStore(INTEL_DIR / "facts.json"), JsonStore(INTEL_DIR / "events.json"))

    # 1) SOURCE
    source_records, alias_report = normalize_sources([it.get("source") for it in sample])
    for sid, rec in source_records.items():
        source_store.upsert(sid, rec)
    name_to_id = {}
    for sid, rec in source_records.items():
        name_to_id[rec["canonical_name"]] = sid
        for a in rec["aliases"]:
            name_to_id[a] = sid

    # 2) DOCUMENT
    doc_items = []  # (document_id, item) — event 단계에서 재사용
    for it in sample:
        sid = name_to_id.get(it.get("source"))
        # document_type 추정은 실제 원문 링크의 도메인을 본다(구글 뉴스 경유는 news.google.com이라
        # 신호가 약하지만, 직접 RSS 소스는 원문 도메인이 그대로 나와 arXiv/정부 도메인 판별에 쓸 수 있다).
        try:
            doc_domain = _domain_from_url(it.get("link", ""))
        except Exception:
            doc_domain = None
        doc = to_document(it, sid, now_iso, domain=doc_domain)
        doc_store.upsert(doc["document_id"], doc)
        doc_items.append((doc["document_id"], it))

    # 3) FACT
    fact_counts = Counter()
    for did, it in doc_items:
        actors = briefing.mx_actors(it) if it.get("title") else []
        fact = make_fact_candidate(it, did, actors[0] if actors else None, now_iso)
        fact_store.upsert(fact["fact_id"], fact)
        fact_counts[fact["status"]] += 1

    # 4) EVENT (보수적 규칙 병합)
    events, doc_event, merge_log = cluster_events(briefing, doc_items, normalized_topic_of, normalized_entities_of)
    for eid, rec in events.items():
        event_store.upsert(eid, rec)

    source_store.save(); doc_store.save(); fact_store.save(); event_store.save()
    (INTEL_DIR / "source_aliases.json").write_text(json.dumps(alias_report, ensure_ascii=False, indent=1), encoding="utf-8")
    (INTEL_DIR / "event_merge_log.json").write_text(json.dumps(merge_log, ensure_ascii=False, indent=1), encoding="utf-8")

    resolved_docs = sum(1 for v in doc_event.values() if v)
    metrics = {
        "input_documents": len(sample),
        "unique_sources": len(source_records),
        "source_alias_merges": len(alias_report),
        "documents_normalized": len(doc_items),
        "fact_candidates": sum(fact_counts.values()),
        "source_verified_facts": fact_counts.get("SOURCE_VERIFIED", 0),
        "summary_derived_facts": fact_counts.get("SUMMARY_DERIVED", 0),
        "insufficient_source": fact_counts.get("INSUFFICIENT_SOURCE", 0),
        "not_extracted": fact_counts.get("NOT_EXTRACTED", 0),
        "event_candidates": len(events),
        "auto_merged_events_documents": resolved_docs,
        "unresolved_documents": len(doc_items) - resolved_docs,
        "duplicates_found_across_days": sum(c - 1 for c in dup_ids.values() if c > 1),
        "processing_time_sec": round(time.time() - t0, 2),
        "gemini_calls_added": 0,
        "claude_calls_added": 0,
    }
    (INTEL_DIR / "pilot_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")
    return metrics, source_records, alias_report, doc_items, fact_store, events, merge_log, doc_event


if __name__ == "__main__":
    m, *_ = run()
    print(json.dumps(m, ensure_ascii=False, indent=1))
