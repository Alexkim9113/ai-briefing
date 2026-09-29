#!/usr/bin/env python3
# PHASE 4B — INTERNAL PRODUCTION EVENT ENGINE. Phase 4A의 Structured Candidate Score를
# 기반으로 채택하되(운영자 지시 2번), 기존 intel/event_service.py/events.json은 건드리지
# 않고 별도 산출물로 만든다(안전한 통합). Public에는 연결하지 않는다.
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "intel"))
sys.path.insert(0, str(ROOT / "intel" / "event_matching"))

from event_matching.signals import compute_signals, canonical_entities, distinctive_terms, action_family  # noqa: E402
from event_matching.score import score_pair, T_CONFIRMED  # noqa: E402
from contamination import blocks_same_event  # noqa: E402
from fingerprint import date_bucket, fingerprint, is_recurring_statement_pair, STATEMENT_CLUSTER_CAP  # noqa: E402
from event_type import classify_event_type, is_gov_actor  # noqa: E402
from primary_document import select_primary  # noqa: E402
from source_diversity import compute as compute_diversity  # noqa: E402
from naming import canonical_event_name  # noqa: E402
from fact_pack import build_fact_pack  # noqa: E402
from overrides import load_overrides, apply_overrides  # noqa: E402
from candidate_reduction import bucket as reduce_candidates  # noqa: E402

INTEL_DIR = ROOT / "intel"
OUT_DIR = Path(__file__).resolve().parent


def load_all_raw_items():
    by_id = {}
    for f in ROOT.glob("data/2026-*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for it in d.get("items", []):
            by_id[it["id"]] = it
    return by_id


def load_facts_by_document():
    facts = json.loads((INTEL_DIR / "facts.json").read_text(encoding="utf-8"))
    by_doc = {}
    for fid, f in facts.items():
        by_doc.setdefault(f["document_id"], f)  # 문서당 fact 1개(현재 fact_service 스펙)
    return by_doc


def pair_decision(a, b):
    """Phase 4A score_pair에 Production 전용 가드(오염 차단, 반복성명 캡 힌트)를 얹는다."""
    if blocks_same_event(a, b):
        return 0.0, "UNRESOLVED", [], ["MARKET_ANALYST_CONTAMINATION_BLOCKED"], compute_signals(a, b)
    return score_pair(a, b)


def build_events(raw_items, documents_by_id):
    doc_ids = [d for d in documents_by_id if d in raw_items]
    items = [(did, raw_items[did]) for did in doc_ids]
    n = len(items)

    doc_state = {}
    confirmed_events, ongoing_issues, candidate_pairs = {}, [], []

    for i in range(n):
        did_a, a = items[i]
        if doc_state.get(did_a) == "CONFIRMED":
            continue
        cluster = [did_a]
        overflow = []  # 반복 성명류에서 cap을 넘어 ONGOING_ISSUE로 빠지는 문서
        for j in range(i + 1, n):
            did_b, b = items[j]
            if doc_state.get(did_b) == "CONFIRMED":
                continue
            score, state, pos, neg, sig = pair_decision(a, b)
            if state == "CONFIRMED":
                if is_recurring_statement_pair(sig) and len(cluster) >= STATEMENT_CLUSTER_CAP:
                    overflow.append(did_b)
                    continue
                cluster.append(did_b)
            elif state == "CANDIDATE":
                candidate_pairs.append({"a": did_a, "b": did_b, "score": score, "state": state,
                                         "positive_evidence": pos, "negative_evidence": neg})

        if len(cluster) > 1:
            eid = f"evtprod_{did_a}"
            ents = canonical_entities(a)
            terms = distinctive_terms(a)
            act = action_family(a)
            doc_type = documents_by_id.get(did_a, {}).get("document_type")
            gov = is_gov_actor(a)
            etype = classify_event_type(act, doc_type, ents, a.get("title", ""), gov)
            db = compute_diversity(cluster, raw_items)
            primary = select_primary(cluster, raw_items, documents_by_id)
            name = canonical_event_name(ents, act, terms)
            confirmed_events[eid] = {
                "event_id": eid, "event_name": name, "event_type": etype,
                "event_date": date_bucket(a), "entities": sorted(ents),
                "action_family": act, "primary_document_id": primary,
                "related_document_ids": cluster, "document_ids": cluster,
                "source_count": db["source_count"], "source_diversity": db["source_diversity"],
                "merge_confidence": T_CONFIRMED, "event_status": "CONFIRMED",
                "event_importance": None,  # 이번 Phase는 hook만(운영자 지시 10번) — 값은 아직 안 채움
                "fingerprint": fingerprint(ents, act, terms, date_bucket(a)),
            }
            for d in cluster:
                doc_state[d] = "CONFIRMED"
            if overflow:
                ongoing_issues.append({
                    "issue_fingerprint": {"entities": sorted(ents), "action_family": act},
                    "anchor_event_id": eid, "overflow_document_ids": overflow,
                    "reason": "RECURRING_STATEMENT_CAP_EXCEEDED",
                })
        else:
            doc_state[did_a] = None

    high_review, low_confidence = reduce_candidates(candidate_pairs)
    return confirmed_events, ongoing_issues, high_review, low_confidence, candidate_pairs


def run():
    raw_items = load_all_raw_items()
    documents_by_id = json.loads((INTEL_DIR / "documents.json").read_text(encoding="utf-8"))
    facts_by_doc = load_facts_by_document()

    confirmed_events, ongoing_issues, high_review, low_confidence, all_candidates = build_events(raw_items, documents_by_id)

    overrides = load_overrides()
    confirmed_events, human_rejected = apply_overrides(confirmed_events, overrides)

    fact_packs = {}
    for eid, ev in confirmed_events.items():
        fact_packs[eid] = build_fact_pack(
            eid, ev["event_name"], ev["event_type"], ev["event_date"], ev["primary_document_id"],
            ev["related_document_ids"], ev["entities"], facts_by_doc)

    OUT_DIR.joinpath("production_events.json").write_text(
        json.dumps(confirmed_events, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    OUT_DIR.joinpath("ongoing_issues.json").write_text(
        json.dumps(ongoing_issues, ensure_ascii=False, indent=1), encoding="utf-8")
    OUT_DIR.joinpath("candidate_high_review.json").write_text(
        json.dumps(high_review, ensure_ascii=False, indent=1), encoding="utf-8")
    OUT_DIR.joinpath("candidate_low_confidence.json").write_text(
        json.dumps(low_confidence, ensure_ascii=False, indent=1), encoding="utf-8")
    OUT_DIR.joinpath("event_fact_packs.json").write_text(
        json.dumps(fact_packs, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")

    doc_sizes = [len(e["document_ids"]) for e in confirmed_events.values()]
    type_dist = {}
    for e in confirmed_events.values():
        type_dist[e["event_type"]] = type_dist.get(e["event_type"], 0) + 1
    div_dist = {}
    for e in confirmed_events.values():
        div_dist[e["source_diversity"]] = div_dist.get(e["source_diversity"], 0) + 1

    metrics = {
        "documents_considered": len([d for d in documents_by_id if d in raw_items]),
        "confirmed_events": len(confirmed_events),
        "documents_absorbed_into_events": sum(doc_sizes),
        "unresolved_documents": len([d for d in documents_by_id if d in raw_items]) - sum(doc_sizes),
        "avg_docs_per_event": round(sum(doc_sizes) / len(doc_sizes), 2) if doc_sizes else 0,
        "max_docs_per_event": max(doc_sizes) if doc_sizes else 0,
        "candidate_high_review": len(high_review), "candidate_low_confidence": len(low_confidence),
        "candidate_total_before_reduction": len(all_candidates),
        "ongoing_issue_groups": len(ongoing_issues),
        "human_rejected": len(human_rejected),
        "event_type_distribution": type_dist, "source_diversity_distribution": div_dist,
        "gemini_calls_added": 0, "claude_calls_added": 0, "embedding_calls": 0, "external_api_calls": 0,
    }
    OUT_DIR.joinpath("production_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")
    return metrics, confirmed_events, ongoing_issues, high_review, low_confidence


if __name__ == "__main__":
    m, *_ = run()
    print(json.dumps(m, ensure_ascii=False, indent=1))
