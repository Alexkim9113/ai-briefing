#!/usr/bin/env python3
# PHASE 4C — CHANGE LAYER Pilot. intel/event_production/production_events.json(읽기 전용)만
# 입력으로 쓴다. 기존 Public/Publication Gate/briefing.py/Production Event 전부 미변경.
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

from schema import new_change_shell, MIN_SUPPORTING_EVENTS  # noqa: E402
from fingerprint import DIRECTION_LABEL_KO  # noqa: E402
from candidate_generation import generate_candidates  # noqa: E402
from evidence import event_quality_record, split_supporting_contradicting  # noqa: E402
from fact_pack import build_change_fact_pack  # noqa: E402
from overrides import load_overrides, apply_overrides  # noqa: E402
from memory import load_existing_changes, upsert_change  # noqa: E402
from source_independence_gate import (  # noqa: E402
    load_documents, independent_evidence_count,
)

EVENT_DIR = ROOT / "intel" / "event_production"


def load_raw_items():
    by_id = {}
    for f in ROOT.glob("data/2026-*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for it in d.get("items", []):
            by_id[it["id"]] = it
    return by_id


def _change_id(object_term, entities):
    key = object_term + "|" + "|".join(sorted(entities))
    return "chg_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def _change_statement(entities, direction, object_term):
    """구조화된 Event/Fact에서 만든 독립적 표현(운영자 지시 22번) — 기사 문장 짜깁기 금지."""
    label = DIRECTION_LABEL_KO.get(direction, "변화")
    ent_str = "·".join(sorted(entities)[:3])
    return f"{ent_str} 등 서로 다른 주체에 걸쳐 '{object_term}' 관련 움직임이 {label} 추세로 관측됨"


def run():
    events = json.loads((EVENT_DIR / "production_events.json").read_text(encoding="utf-8"))
    for eid, ev in events.items():
        ev["event_id"] = eid
    event_fact_packs = json.loads((EVENT_DIR / "event_fact_packs.json").read_text(encoding="utf-8"))
    raw_items = load_raw_items()

    candidates = generate_candidates(events, raw_items)
    documents_by_id = load_documents()

    existing = load_existing_changes()
    changes = {}
    change_evidence = {}
    fact_packs = {}
    independence_rejections = []
    for cand in candidates:
        cid = _change_id(cand["object_term"], cand["entities"])
        supporting, contradicting = split_supporting_contradicting(cand, events)
        if len(supporting) < MIN_SUPPORTING_EVENTS:
            continue  # 반대 증거를 빼고 나니 최소 조건 미달 — Change로 성립 안 함(운영자 지시 2번)

        # PHASE M.5 — source independence gate (ADDITIVE ONLY, never lowers
        # MIN_SUPPORTING_EVENTS): collapse supporting Events whose documents share an origin
        # (SHARED_ORIGIN/DERIVED_FROM_SAME_SOURCE) into one evidence family before counting.
        # A candidate whose raw event count clears MIN_SUPPORTING_EVENTS only because several
        # of its Events trace back to the same underlying source is rejected here.
        indep_count = independent_evidence_count(supporting, events, documents_by_id)
        if indep_count < MIN_SUPPORTING_EVENTS:
            independence_rejections.append({
                "object_term": cand["object_term"], "entities": cand["entities"],
                "raw_event_count": len(supporting), "independent_evidence_count": indep_count,
            })
            continue

        name = f"{cand['object_term']} 관련 변화"
        statement = _change_statement(cand["entities"], cand["direction"], cand["object_term"])
        shell = new_change_shell(cid, name, statement, cand["direction"])
        shell.update({
            "supporting_event_ids": supporting, "contradicting_event_ids": contradicting,
            "event_count": len(supporting),
            "independent_source_count": indep_count,  # PHASE M.5: gated, not raw len(supporting)
            "entity_diversity": cand["entity_diversity"], "domain_diversity": len(cand["event_types"]),
            "time_span_days": _span_days(cand["first_seen"], cand["last_seen"]),
            "topics": cand["event_types"], "domains": cand["event_types"], "entities": cand["entities"],
            "first_seen": cand["first_seen"], "last_seen": cand["last_seen"],
        })
        shell["evidence_strength"] = _evidence_strength(shell)
        shell["change_confidence"] = _confidence_label(shell)
        shell = upsert_change(existing, cid, shell)
        changes[cid] = shell

        change_evidence[cid] = [event_quality_record(eid, events[eid], events[eid].get("event_status", "AUTO_CONFIRMED"))
                                 for eid in supporting]
        fact_packs[cid] = build_change_fact_pack(cid, statement, supporting, contradicting,
                                                  event_fact_packs, cand["entities"],
                                                  cand["first_seen"], cand["last_seen"])

    overrides = load_overrides()
    changes = apply_overrides(changes, overrides)

    HERE.joinpath("change_candidates.json").write_text(
        json.dumps(candidates, ensure_ascii=False, indent=1), encoding="utf-8")
    HERE.joinpath("changes.json").write_text(
        json.dumps(changes, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    HERE.joinpath("change_evidence.json").write_text(
        json.dumps(change_evidence, ensure_ascii=False, indent=1), encoding="utf-8")
    HERE.joinpath("change_history.json").write_text(
        json.dumps({cid: c["status_history"] for cid, c in changes.items()}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    HERE.joinpath("change_fact_packs.json").write_text(
        json.dumps(fact_packs, ensure_ascii=False, indent=1), encoding="utf-8")

    metrics = {
        "input_confirmed_events": len(events),
        "raw_candidate_groups": len(candidates),
        "changes_created": len(changes),
        "changes_by_status": _count_by(changes, "status"),
        "changes_by_direction": _count_by(changes, "direction"),
        "independence_gate_rejections": len(independence_rejections),
        "independence_gate_rejection_details": independence_rejections,
        "gemini_calls_added": 0, "claude_calls_added": 0, "embedding_calls": 0, "external_api_calls": 0,
    }
    HERE.joinpath("change_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")
    return metrics, candidates, changes


def _span_days(first, last):
    if not first or not last:
        return 0
    from datetime import date
    try:
        f = date.fromisoformat(first[:10])
        l = date.fromisoformat(last[:10])
        return abs((l - f).days)
    except Exception:
        return 0


def _evidence_strength(shell):
    score = shell["event_count"] + shell["entity_diversity"] + shell["domain_diversity"]
    if shell["contradicting_event_ids"]:
        score -= len(shell["contradicting_event_ids"])
    return score


def _confidence_label(shell):
    s = shell["evidence_strength"]
    if s >= 6:
        return "HIGH"
    if s >= 3:
        return "MEDIUM"
    return "LOW"


def _count_by(changes, field):
    out = {}
    for c in changes.values():
        out[c[field]] = out.get(c[field], 0) + 1
    return out


if __name__ == "__main__":
    m, *_ = run()
    print(json.dumps(m, ensure_ascii=False, indent=1))
