#!/usr/bin/env python3
# PHASE 4A EVENT MATCHING PILOT 실행기.
# 1) Gold Test Set으로 Old Engine vs New Pilot Precision/Recall 비교.
# 2) 통과 후 intel/documents.json(기존 Phase 3-A 샘플, 읽기 전용)에 Shadow Run.
# 기존 intel/event_service.py, events.json은 절대 덮어쓰지 않는다(운영자 지시 15).
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # intel/ (document_service 등)
sys.path.insert(0, str(ROOT))

from event_matching.gold_set import TRUE_POSITIVE_PAIRS, HARD_NEGATIVE_PAIRS  # noqa: E402
from event_matching.old_engine import old_engine_merge  # noqa: E402
from event_matching.score import score_pair  # noqa: E402

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


def evaluate_gold_set(raw_items):
    rows = []
    for did_a, did_b, reason in TRUE_POSITIVE_PAIRS:
        a, b = raw_items.get(did_a), raw_items.get(did_b)
        if not a or not b:
            rows.append({"pair": [did_a, did_b], "label": "TRUE_POSITIVE", "reason": reason, "missing": True})
            continue
        old = old_engine_merge(a, b)
        score, state, pos, neg, sig = score_pair(a, b)
        rows.append({"pair": [did_a, did_b], "label": "TRUE_POSITIVE", "reason": reason,
                     "old_engine_merged": old, "new_score": score, "new_state": state,
                     "positive_evidence": pos, "negative_evidence": neg})
    for did_a, did_b, reason in HARD_NEGATIVE_PAIRS:
        a, b = raw_items.get(did_a), raw_items.get(did_b)
        if not a or not b:
            rows.append({"pair": [did_a, did_b], "label": "HARD_NEGATIVE", "reason": reason, "missing": True})
            continue
        old = old_engine_merge(a, b)
        score, state, pos, neg, sig = score_pair(a, b)
        rows.append({"pair": [did_a, did_b], "label": "HARD_NEGATIVE", "reason": reason,
                     "old_engine_merged": old, "new_score": score, "new_state": state,
                     "positive_evidence": pos, "negative_evidence": neg})

    def metrics(engine_key, is_positive_fn):
        tp = fp = tn = fn = 0
        for r in rows:
            if r.get("missing"):
                continue
            actual_positive = r["label"] == "TRUE_POSITIVE"
            predicted_positive = is_positive_fn(r)
            if actual_positive and predicted_positive:
                tp += 1
            elif not actual_positive and predicted_positive:
                fp += 1
            elif not actual_positive and not predicted_positive:
                tn += 1
            else:
                fn += 1
        precision = tp / (tp + fp) if (tp + fp) else None
        recall = tp / (tp + fn) if (tp + fn) else None
        return {"true_positives": tp, "false_positives": fp, "true_negatives": tn, "false_negatives": fn,
                "precision": round(precision, 3) if precision is not None else None,
                "recall": round(recall, 3) if recall is not None else None}

    old_metrics = metrics("old", lambda r: r["old_engine_merged"])
    new_metrics = metrics("new", lambda r: r["new_state"] == "CONFIRMED")
    new_metrics_incl_candidate = metrics("new_incl_candidate", lambda r: r["new_state"] in ("CONFIRMED", "CANDIDATE"))
    return rows, old_metrics, new_metrics, new_metrics_incl_candidate


def shadow_run(raw_items):
    """intel/documents.json 문서 집합(Phase 3-A 샘플)에 새 Pairwise Score를 전수 적용.
    O(n^2)이지만 Pilot 규모(수백 건)에서는 충분히 빠르다 — 운영 파이프라인이 아니라 실험."""
    documents = json.loads((INTEL_DIR / "documents.json").read_text(encoding="utf-8"))
    doc_ids = list(documents.keys())
    items = [(did, raw_items[did]) for did in doc_ids if did in raw_items]

    n = len(items)
    confirmed_clusters = {}
    candidate_pairs = []
    doc_state = {}
    for i in range(n):
        did_a, a = items[i]
        if did_a in doc_state and doc_state[did_a] == "CONFIRMED":
            continue
        cluster = [did_a]
        for j in range(i + 1, n):
            did_b, b = items[j]
            if doc_state.get(did_b) == "CONFIRMED":
                continue
            score, state, pos, neg, sig = score_pair(a, b)
            if state == "CONFIRMED":
                cluster.append(did_b)
            elif state == "CANDIDATE":
                candidate_pairs.append({"a": did_a, "b": did_b, "score": score, "state": state,
                                         "positive_evidence": pos, "negative_evidence": neg})
        if len(cluster) > 1:
            eid = f"evtp_{did_a}"
            confirmed_clusters[eid] = {"event_id": eid, "document_ids": cluster,
                                        "event_name": (a.get("title_ko") or a["title"])[:80],
                                        "status": "CONFIRMED"}
            for d in cluster:
                doc_state[d] = "CONFIRMED"

    return confirmed_clusters, candidate_pairs, n


def run():
    raw_items = load_all_raw_items()
    gold_rows, old_metrics, new_metrics, new_metrics_incl_candidate = evaluate_gold_set(raw_items)
    (OUT_DIR / "gold_set_evaluation.json").write_text(
        json.dumps({"rows": gold_rows, "old_engine_metrics": old_metrics,
                    "new_pilot_metrics_confirmed_only": new_metrics,
                    "new_pilot_metrics_confirmed_or_candidate": new_metrics_incl_candidate},
                   ensure_ascii=False, indent=1), encoding="utf-8")

    confirmed_clusters, candidate_pairs, n_docs = shadow_run(raw_items)
    (OUT_DIR / "event_pilot.json").write_text(
        json.dumps(confirmed_clusters, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    (OUT_DIR / "event_candidates.json").write_text(
        json.dumps(candidate_pairs, ensure_ascii=False, indent=1), encoding="utf-8")

    metrics = {
        "gold_set_size": len(TRUE_POSITIVE_PAIRS) + len(HARD_NEGATIVE_PAIRS),
        "old_engine": old_metrics, "new_pilot_confirmed_only": new_metrics,
        "new_pilot_confirmed_or_candidate": new_metrics_incl_candidate,
        "shadow_run_documents": n_docs,
        "shadow_run_confirmed_events": len(confirmed_clusters),
        "shadow_run_confirmed_documents": sum(len(c["document_ids"]) for c in confirmed_clusters.values()),
        "shadow_run_candidate_pairs": len(candidate_pairs),
        "gemini_calls_added": 0, "claude_calls_added": 0, "embedding_calls": 0, "external_api_calls": 0,
    }
    (OUT_DIR / "event_pilot_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")
    return metrics, gold_rows, confirmed_clusters, candidate_pairs


if __name__ == "__main__":
    m, *_ = run()
    print(json.dumps(m, ensure_ascii=False, indent=1))
