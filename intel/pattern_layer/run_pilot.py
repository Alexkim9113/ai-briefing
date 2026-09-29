#!/usr/bin/env python3
# PHASE 5B — PATTERN INTELLIGENCE FOUNDATION Pilot. intel/change_layer/changes.json과
# intel/signal_layer/signals.json(둘 다 읽기 전용)만 입력으로 쓴다. Public/Publication
# Gate/briefing.py/Event/Change/Signal Layer 전부 미변경.
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

from schema import new_pattern_shell  # noqa: E402
from mechanism import relation_for_direction  # noqa: E402
from candidate_generation import generate_pattern_candidates  # noqa: E402
from evidence import find_contradicting_changes, change_quality_record  # noqa: E402
from fact_pack import build_pattern_fact_pack  # noqa: E402
from overrides import load_overrides, apply_overrides  # noqa: E402
from memory import load_existing_patterns, upsert_pattern  # noqa: E402

CHANGE_DIR = ROOT / "intel" / "change_layer"
SIGNAL_DIR = ROOT / "intel" / "signal_layer"


def load_active_changes():
    all_changes = json.loads((CHANGE_DIR / "changes.json").read_text(encoding="utf-8"))
    return {cid: c for cid, c in all_changes.items()
            if c.get("status") != "REJECTED" and c.get("override_status") != "HUMAN_REJECTED"}


def load_active_signals():
    path = SIGNAL_DIR / "signals.json"
    if not path.exists():
        return {}
    all_signals = json.loads(path.read_text(encoding="utf-8"))
    return {sid: s for sid, s in all_signals.items()
            if s.get("status") != "REJECTED" and s.get("override_status") != "HUMAN_REJECTED"}


def _pattern_id(mechanism_key, change_ids):
    key = json.dumps(mechanism_key, sort_keys=True) + "|" + "|".join(sorted(change_ids))
    return "pat_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def _pattern_statement(cand):
    dims = "·".join(cand["mechanism_key"]["dimensions"])
    rel = cand["mechanism_key"]["relation"]
    scope = "서로 다른 Domain에 걸쳐" if cand["is_cross_domain"] else "복수의 독립적 Change에서"
    return f"{scope} '{dims}' 축에서 '{rel}' 관계 구조가 {cand['change_count']}건 반복 관측됨"


def _evidence_strength(cand):
    return cand["change_count"] + cand["entity_diversity"] + cand["domain_diversity"]


def _confidence_label(strength, has_counter_evidence):
    s = strength - (2 if has_counter_evidence else 0)
    if s >= 7:
        return "HIGH"
    if s >= 4:
        return "MEDIUM"
    return "LOW"


def _span_days(first, last):
    if not first or not last:
        return 0
    from datetime import date
    try:
        f, l = date.fromisoformat(first[:10]), date.fromisoformat(last[:10])
        return abs((l - f).days)
    except Exception:
        return 0


def run(changes_override=None, signals_override=None, out_dir=None,
        previous_snapshot_path=None, overrides_path=None):
    """*_override/out_dir/*_path는 synthetic fixture 테스트 전용 격리 경로. 기본값은 실제 운영 경로."""
    out_dir = Path(out_dir) if out_dir else HERE
    active_changes = changes_override if changes_override is not None else load_active_changes()
    active_signals = signals_override if signals_override is not None else load_active_signals()

    change_fact_packs = {}
    cfp_path = CHANGE_DIR / "change_fact_packs.json"
    if changes_override is None and cfp_path.exists():
        change_fact_packs = json.loads(cfp_path.read_text(encoding="utf-8"))

    candidates = generate_pattern_candidates(active_changes, active_signals)

    existing = load_existing_patterns(Path(previous_snapshot_path) if previous_snapshot_path
                                       else out_dir / "patterns.json")

    patterns, pattern_evidence, fact_packs = {}, {}, {}
    for cand in candidates:
        pid = _pattern_id(cand["mechanism_key"], cand["change_ids"])
        relation = cand["mechanism_key"]["relation"]
        contradicting = find_contradicting_changes(cand["mechanism_key"]["dimensions"], relation,
                                                     active_changes, set(cand["change_ids"]))

        strength = _evidence_strength(cand)
        confidence = _confidence_label(strength, bool(contradicting))
        statement = _pattern_statement(cand)

        shell = new_pattern_shell(pid, f"{'·'.join(cand['mechanism_key']['dimensions'])} 반복 구조",
                                   statement, cand["pattern_type"], cand["mechanism_key"]["dimensions"])
        shell.update({
            "relation_type": relation,
            "supporting_change_ids": cand["change_ids"], "supporting_signal_ids": cand["signal_ids"],
            "contradicting_change_ids": contradicting, "contradicting_signal_ids": [],
            "domains": cand["domains"], "entities": cand["entities"],
            "first_seen": cand["first_seen"], "last_seen": cand["last_seen"],
            "time_span_days": _span_days(cand["first_seen"], cand["last_seen"]),
            "change_count": cand["change_count"], "signal_count": cand["signal_count"],
            "domain_diversity": cand["domain_diversity"], "entity_diversity": cand["entity_diversity"],
            "evidence_strength": strength, "pattern_confidence": confidence,
            "status": "CANDIDATE",
        })
        shell = upsert_pattern(existing, pid, shell)
        patterns[pid] = shell

        pattern_evidence[pid] = [change_quality_record(cid, active_changes[cid]) for cid in cand["change_ids"]]
        fact_packs[pid] = build_pattern_fact_pack(
            pid, statement, cand["change_ids"], cand["signal_ids"], contradicting, [],
            change_fact_packs, cand["entities"], cand["domains"], cand["domains"],
            cand["mechanism_key"]["dimensions"], cand["first_seen"], cand["last_seen"])

    # 이번 실행에서 재감지되지 않은 기존 Pattern도 보존한다(Pattern Memory — History 단절 방지).
    merged = dict(existing)
    merged.update(patterns)

    overrides = load_overrides(Path(overrides_path)) if overrides_path else load_overrides()
    merged = apply_overrides(merged, overrides)

    out_dir.joinpath("pattern_candidates.json").write_text(
        json.dumps(candidates, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    out_dir.joinpath("patterns.json").write_text(
        json.dumps(merged, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    out_dir.joinpath("pattern_evidence.json").write_text(
        json.dumps(pattern_evidence, ensure_ascii=False, indent=1), encoding="utf-8")
    out_dir.joinpath("pattern_history.json").write_text(
        json.dumps({pid: p["status_history"] for pid, p in merged.items()}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    out_dir.joinpath("pattern_fact_packs.json").write_text(
        json.dumps(fact_packs, ensure_ascii=False, indent=1), encoding="utf-8")

    readiness = {
        "supports_weekly_queries": ["NEW_PATTERNS", "STRENGTHENING_PATTERNS", "WEAKENING_PATTERNS",
                                     "CROSS_DOMAIN_PATTERNS", "PATTERNS_WITH_COUNTER_EVIDENCE"],
        "supports_futures_chain": "PATTERN -> STRUCTURAL_CHANGE (not implemented this phase)",
        "structural_change_generated": False,
        "forecast_generated": False,
    }
    out_dir.joinpath("pattern_readiness.json").write_text(
        json.dumps(readiness, ensure_ascii=False, indent=1), encoding="utf-8")

    metrics = {
        "input_active_changes": len(active_changes),
        "input_active_signals": len(active_signals),
        "pattern_candidates_generated": len(candidates),
        "patterns_created_or_updated": len(patterns),
        "patterns_total": len(merged),
        "patterns_by_type": _count_by(merged, "pattern_type"),
        "patterns_by_status": _count_by(merged, "status"),
        "gemini_calls_added": 0, "claude_calls_added": 0, "embedding_calls": 0, "external_api_calls": 0,
    }
    out_dir.joinpath("pattern_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")
    return metrics, merged


def _count_by(d, field):
    out = {}
    for v in d.values():
        out[v[field]] = out.get(v[field], 0) + 1
    return out


if __name__ == "__main__":
    m, _ = run()
    print(json.dumps(m, ensure_ascii=False, indent=1))
