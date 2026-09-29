#!/usr/bin/env python3
# PHASE 5A — SIGNAL FOUNDATION Pilot. intel/change_layer/changes.json(읽기 전용)만 입력으로
# 쓴다. Public/Publication Gate/briefing.py/Event/Change Layer 전부 미변경.
# REJECTED(override_status=HUMAN_REJECTED) Change는 Signal 감지 대상에서 제외한다
# (운영자 지시: Human Override는 자동 재실행이 무시할 수 없다).
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

from schema import new_signal_shell  # noqa: E402
from detection import detect_signals_for_change, maturity_for  # noqa: E402
from memory import load_existing_signals, upsert_signal  # noqa: E402
from overrides import load_overrides, apply_overrides  # noqa: E402
from fact_pack import build_signal_fact_pack  # noqa: E402

CHANGE_DIR = ROOT / "intel" / "change_layer"


def load_active_changes():
    """REJECTED Change는 애초에 Signal 감지 대상이 아니다(Acceptance 1,2번)."""
    all_changes = json.loads((CHANGE_DIR / "changes.json").read_text(encoding="utf-8"))
    return {cid: c for cid, c in all_changes.items()
            if c.get("status") != "REJECTED" and c.get("override_status") != "HUMAN_REJECTED"}


def _signal_id(change_id, signal_type):
    key = change_id + "|" + signal_type
    return "sig_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def _signal_name(change, signal_type):
    ent = "·".join(sorted(change.get("entities", []))[:2]) or change.get("change_name", "")
    return f"{ent} — {change.get('change_name', '')} ({signal_type})"


def run(previous_snapshot_path=None, changes_override=None, out_dir=None, overrides_path=None):
    """previous_snapshot_path/changes_override/out_dir/overrides_path는 synthetic fixture
    테스트에서만 실 파일 대신 격리된 경로를 넘기기 위한 것. 기본값은 실제 운영 경로."""
    out_dir = out_dir or HERE
    active_changes = changes_override if changes_override is not None else load_active_changes()

    existing_signals = load_existing_signals(Path(previous_snapshot_path) if previous_snapshot_path
                                              else HERE / "signals.json")
    # baseline: 직전 실행에서 이 change_id에 대해 관측했던 지표 스냅샷(운영자 지시 8번).
    previous_change_snapshot = {}
    for sid, sig in existing_signals.items():
        for cid in sig.get("change_ids", []):
            baseline = sig.get("baseline", {})
            cur = baseline.get("current_state")
            if cur:
                previous_change_snapshot[cid] = cur

    candidates = []
    fact_packs = {}
    for cid, change in active_changes.items():
        cand_list = detect_signals_for_change(change, previous_change_snapshot)
        for cand in cand_list:
            candidates.append({"change": change, "candidate": cand})

    # 이번 실행에서 새로 감지되지 않은 기존 Signal도 그대로 보존한다(Signal Memory —
    # 재감지되지 않았다고 지우지 않는다; 단, 더 이상 활성이 아닌 change의 Signal은 change_ids가
    # active_changes에 없어도 기록 자체는 유지해 History가 끊기지 않게 한다).
    signals = dict(existing_signals)
    for item in candidates:
        change, cand = item["change"], item["candidate"]
        cid = change["change_id"]
        stype = cand["signal_type"]
        sid = _signal_id(cid, stype)

        shell = new_signal_shell(sid, _signal_name(change, stype), stype, [cid])
        prev_sig = existing_signals.get(sid)
        prev_maturity = prev_sig.get("maturity") if prev_sig else None
        shell["maturity"] = maturity_for(stype, prev_maturity)
        shell["direction"] = change.get("direction")
        shell["supporting_event_ids"] = change.get("supporting_event_ids", [])
        shell["contradicting_event_ids"] = change.get("contradicting_event_ids", [])
        shell["entity_diversity"] = change.get("entity_diversity", 0)
        shell["domain_diversity"] = change.get("domain_diversity", 0)
        shell["evidence_strength"] = change.get("evidence_strength")
        shell["signal_confidence"] = _confidence_label(change, cand)
        shell["status"] = "CANDIDATE"
        shell["baseline"] = {
            "previous_state": previous_change_snapshot.get(cid),
            "current_state": {
                "event_count": change.get("event_count"),
                "entity_diversity": change.get("entity_diversity"),
                "domain_diversity": change.get("domain_diversity"),
                "contradicting_event_ids": change.get("contradicting_event_ids", []),
                "direction": change.get("direction"),
                "status": change.get("status"),
                "updated_at": change.get("updated_at"),
            },
            "delta": cand.get("delta"),
        }
        shell = upsert_signal(existing_signals, sid, shell)
        signals[sid] = shell

        fact_packs[sid] = build_signal_fact_pack(
            sid, stype, shell["maturity"], [cid],
            change.get("supporting_event_ids", []), change.get("contradicting_event_ids", []),
            {}, change.get("entities", []), change.get("domains", []), change.get("topics", []),
            change.get("first_seen"), change.get("last_seen"))

    overrides = load_overrides(Path(overrides_path)) if overrides_path else load_overrides()
    signals = apply_overrides(signals, overrides)

    out_dir = Path(out_dir)
    out_dir.joinpath("signal_candidates.json").write_text(
        json.dumps([{"change_id": c["change"]["change_id"], **c["candidate"]} for c in candidates],
                   ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    out_dir.joinpath("signals.json").write_text(
        json.dumps(signals, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    out_dir.joinpath("signal_history.json").write_text(
        json.dumps({sid: s["status_history"] for sid, s in signals.items()}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    out_dir.joinpath("signal_evidence.json").write_text(
        json.dumps({sid: s["baseline"] for sid, s in signals.items()}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    out_dir.joinpath("signal_fact_packs.json").write_text(
        json.dumps(fact_packs, ensure_ascii=False, indent=1), encoding="utf-8")

    metrics = {
        "input_active_changes": len(active_changes),
        "input_rejected_changes_excluded": len(json.loads((CHANGE_DIR / "changes.json").read_text(encoding="utf-8"))) - len(active_changes) if changes_override is None else 0,
        "signal_candidates_generated": len(candidates),
        "signals_created": len(signals),
        "signals_by_type": _count_by(signals, "signal_type"),
        "signals_by_status": _count_by(signals, "status"),
        "gemini_calls_added": 0, "claude_calls_added": 0, "embedding_calls": 0, "external_api_calls": 0,
    }
    out_dir.joinpath("signal_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")
    return metrics, signals


def _confidence_label(change, cand):
    """가짜 확률 금지(운영자 지시 13번) — Change confidence + 반대증거 유무로만 LOW/MEDIUM/HIGH."""
    base = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}.get(change.get("change_confidence", "LOW"), 0)
    if cand["signal_type"] in ("COUNTER_EVIDENCE_RISING", "WEAKENING"):
        base = max(0, base - 1)
    return ["LOW", "MEDIUM", "HIGH"][base]


def _count_by(signals, field):
    out = {}
    for s in signals.values():
        out[s[field]] = out.get(s[field], 0) + 1
    return out


if __name__ == "__main__":
    m, _ = run()
    print(json.dumps(m, ensure_ascii=False, indent=1))
