#!/usr/bin/env python3
# PHASE 5C — STRUCTURAL CHANGE FOUNDATION Pilot. intel/pattern_layer/patterns.json,
# intel/change_layer/changes.json, intel/signal_layer/signals.json을 읽기 전용으로만 쓴다.
# Public/Publication Gate/briefing.py/Evidence/Fact/Event/Change/Signal/Pattern 전부 미변경.
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

from schema import new_structural_change_shell  # noqa: E402
from transition import structural_change_type_for  # noqa: E402
from candidate_generation import generate_structural_candidates  # noqa: E402
from evidence import find_contradicting_patterns, pattern_quality_record  # noqa: E402
from fact_pack import build_structural_fact_pack  # noqa: E402
from overrides import load_overrides, apply_overrides  # noqa: E402
from memory import load_existing, upsert_structural_change  # noqa: E402

PATTERN_DIR = ROOT / "intel" / "pattern_layer"
CHANGE_DIR = ROOT / "intel" / "change_layer"


def load_active_patterns():
    all_patterns = json.loads((PATTERN_DIR / "patterns.json").read_text(encoding="utf-8"))
    return {pid: p for pid, p in all_patterns.items()
            if p.get("status") != "REJECTED" and p.get("override_status") != "HUMAN_REJECTED"}


def load_changes_for_lineage():
    path = CHANGE_DIR / "changes.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _sc_id(transition_key, pattern_ids):
    key = json.dumps(transition_key, sort_keys=True) + "|" + "|".join(sorted(pattern_ids))
    return "sc_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def _statement(cand):
    frm, to = cand["transition_key"]["from_state"], cand["transition_key"]["to_state"]
    scope = "서로 다른 사회적 영역(Domain)에 걸쳐" if cand["is_cross_domain"] else "복수의 독립적 Pattern에서"
    if frm and to:
        return f"{scope} '{frm}' 상태에서 '{to}' 상태로의 구조적 전환이 {cand['independent_pattern_count']}개 Pattern에 걸쳐 관측됨"
    return f"{scope} '{cand['transition_key']['dimension']}' 축의 구조적 재편이 {cand['independent_pattern_count']}개 Pattern에 걸쳐 관측됨(방향 미확정)"


def _evidence_strength(cand):
    strength = (cand["independent_pattern_count"] + cand["independent_change_count"]
                + cand["entity_diversity"] + cand["domain_diversity"])
    if cand["independent_event_count"]:
        strength += 1  # lineage가 실제로 확인된 경우만 가점 — 없으면 추정하지 않음(운영자 지시 14번)
    return strength


def _confidence_label(strength, overlap_ratio, has_counter_evidence, source_independence_unknown):
    s = strength
    if overlap_ratio and overlap_ratio > 0.3:
        s -= 2
    if has_counter_evidence:
        s -= 2
    # Source independence가 UNKNOWN이면 있는 것처럼 점수를 주지 않는다(운영자 지시 18번) —
    # 상한을 MEDIUM으로 제한.
    if s >= 8 and not source_independence_unknown:
        return "HIGH"
    if s >= 8:
        return "MEDIUM"
    if s >= 4:
        return "MEDIUM"
    return "LOW"


def _span_days(first, last):
    if not first or not last:
        return 0
    from datetime import date
    try:
        f, l = date.fromisoformat(str(first)[:10]), date.fromisoformat(str(last)[:10])
        return abs((l - f).days)
    except Exception:
        return 0


def run(patterns_override=None, changes_override=None, out_dir=None,
        previous_snapshot_path=None, overrides_path=None):
    """*_override/out_dir/*_path는 synthetic fixture 전용 격리 경로. 기본값은 실제 운영 경로."""
    out_dir = Path(out_dir) if out_dir else HERE
    active_patterns = patterns_override if patterns_override is not None else load_active_patterns()
    changes = changes_override if changes_override is not None else load_changes_for_lineage()

    pattern_fact_packs = {}
    pfp_path = PATTERN_DIR / "pattern_fact_packs.json"
    if patterns_override is None and pfp_path.exists():
        pattern_fact_packs = json.loads(pfp_path.read_text(encoding="utf-8"))

    candidates = generate_structural_candidates(active_patterns, changes)

    existing = load_existing(Path(previous_snapshot_path) if previous_snapshot_path
                              else out_dir / "structural_changes.json")

    structural_changes, sc_evidence, fact_packs = {}, {}, {}
    for cand in candidates:
        scid = _sc_id(cand["transition_key"], cand["pattern_ids"])
        dim, rel = cand["transition_key"]["dimension"], cand["transition_key"]["relation"]
        contradicting = find_contradicting_patterns(dim, rel, active_patterns, set(cand["pattern_ids"]))

        strength = _evidence_strength(cand)
        source_unknown = cand["independent_event_count"] is None
        confidence = _confidence_label(strength, cand["pattern_overlap_ratio"], bool(contradicting), source_unknown)
        sc_type = structural_change_type_for([dim], cand["is_cross_domain"])
        statement = _statement(cand)

        shell = new_structural_change_shell(
            scid, f"{dim} 구조적 전환", statement, sc_type, [dim],
            cand["transition_key"]["from_state"], cand["transition_key"]["to_state"])
        shell.update({
            "event_types": cand["event_types"], "domains": cand["domains"],
            "supporting_pattern_ids": cand["pattern_ids"], "supporting_signal_ids": cand["signal_ids"],
            "supporting_change_ids": cand["change_ids"],
            "contradicting_pattern_ids": contradicting, "contradicting_signal_ids": [],
            "contradicting_change_ids": [],
            "entities": cand["entities"], "institutions": [], "resources": [],
            "first_seen": cand["first_seen"], "last_seen": cand["last_seen"],
            "time_span_days": _span_days(cand["first_seen"], cand["last_seen"]),
            "pattern_count": cand["independent_pattern_count"],
            "independent_pattern_count": cand["independent_pattern_count"],
            "independent_signal_count": cand["independent_signal_count"],
            "independent_change_count": cand["independent_change_count"],
            "independent_event_count": cand["independent_event_count"],  # None이면 UNKNOWN 유지
            "independent_document_count": None,  # lineage 없음 — 운영자 지시 0-D, 14번
            "independent_source_count": None,     # Source lineage 없음 — 절대 추정 금지
            "domain_diversity": cand["domain_diversity"], "event_type_diversity": cand["event_type_diversity"],
            "entity_diversity": cand["entity_diversity"],
            "pattern_overlap_ratio": cand["pattern_overlap_ratio"],
            "evidence_strength": strength, "structural_confidence": confidence,
            "status": "CANDIDATE",
        })
        shell = upsert_structural_change(existing, scid, shell)
        structural_changes[scid] = shell

        sc_evidence[scid] = {
            "patterns": [pattern_quality_record(pid, active_patterns[pid]) for pid in cand["pattern_ids"]],
            "independent_change_count": cand["independent_change_count"],
            "event_types": cand["event_types"], "domains": cand["domains"],
            "domain_diversity": cand["domain_diversity"], "event_type_diversity": cand["event_type_diversity"],
            "time_span_days": shell["time_span_days"], "evidence_strength": strength,
            "lineage_completeness": "EVENT_LEVEL_KNOWN" if cand["independent_event_count"] is not None else "UNKNOWN",
        }
        fact_packs[scid] = build_structural_fact_pack(
            scid, statement, shell["from_state"], shell["to_state"], [dim],
            cand["event_types"], cand["domains"], cand["pattern_ids"], cand["signal_ids"],
            cand["change_ids"], contradicting, [], [], pattern_fact_packs,
            cand["entities"],
            {"independent_pattern_count": cand["independent_pattern_count"],
             "independent_change_count": cand["independent_change_count"],
             "independent_signal_count": cand["independent_signal_count"],
             "independent_event_count": cand["independent_event_count"],
             "independent_document_count": None, "independent_source_count": None},
            cand["first_seen"], cand["last_seen"])

    # 이번 실행에서 재감지되지 않은 기존 Structural Change도 보존한다(Memory — History 단절 방지).
    merged = dict(existing)
    merged.update(structural_changes)

    overrides = load_overrides(Path(overrides_path)) if overrides_path else load_overrides()
    merged = apply_overrides(merged, overrides)

    out_dir.joinpath("structural_change_candidates.json").write_text(
        json.dumps(candidates, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    out_dir.joinpath("structural_changes.json").write_text(
        json.dumps(merged, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    out_dir.joinpath("structural_change_evidence.json").write_text(
        json.dumps(sc_evidence, ensure_ascii=False, indent=1), encoding="utf-8")
    out_dir.joinpath("structural_change_history.json").write_text(
        json.dumps({scid: sc["status_history"] for scid, sc in merged.items()}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    out_dir.joinpath("structural_change_fact_packs.json").write_text(
        json.dumps(fact_packs, ensure_ascii=False, indent=1), encoding="utf-8")

    readiness = {
        "supports_weekly_queries": ["NEW_STRUCTURAL_CHANGES", "STRENGTHENING_STRUCTURAL_CHANGES",
                                     "WEAKENING_STRUCTURAL_CHANGES", "REVERSALS", "NEW_COUNTER_EVIDENCE",
                                     "CONFIDENCE_CHANGES", "VIEW_REVISIONS"],
        "supports_operator_queries": ["dimensions", "from_state", "to_state", "time", "domains",
                                       "event_types", "entities", "institutions", "resources"],
        "supports_futures_chain": "STRUCTURAL_CHANGE -> DRIVER (not implemented this phase)",
        "driver_generated": False, "uncertainty_generated": False, "scenario_generated": False,
        "second_order_effects_generated": False, "historical_analogies_generated": False,
    }
    out_dir.joinpath("structural_change_readiness.json").write_text(
        json.dumps(readiness, ensure_ascii=False, indent=1), encoding="utf-8")

    metrics = {
        "input_active_patterns": len(active_patterns),
        "input_changes_for_lineage": len(changes),
        "structural_change_candidates_generated": len(candidates),
        "structural_changes_created_or_updated": len(structural_changes),
        "structural_changes_total": len(merged),
        "structural_changes_by_type": _count_by(merged, "structural_change_type"),
        "structural_changes_by_status": _count_by(merged, "status"),
        "gemini_calls_added": 0, "claude_calls_added": 0, "embedding_calls": 0, "external_api_calls": 0,
    }
    out_dir.joinpath("structural_change_metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")
    return metrics, merged


def _count_by(d, field):
    out = {}
    for v in d.values():
        out[v[field]] = out.get(v[field], 0) + 1
    return out


if __name__ == "__main__":
    m, _ = run()
    print(json.dumps(m, ensure_ascii=False, indent=1))
