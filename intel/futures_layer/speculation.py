# PHASE 5F — Speculation Level/Ceiling(운영자 지시 47~48번). Evidence에서 얼마나 멀리
# 떨어졌는지를 lineage distance + assumption 수 + unsupported transition 수로 계산한다 —
# 객체 종류별로 임의 고정하지 않는다.
from schema import SPECULATION_LEVELS


def compute_speculation_level(lineage_distance, assumption_count, unsupported_transitions):
    score = lineage_distance + assumption_count + (2 * unsupported_transitions)
    if score >= 5:
        return "HIGH"
    if score >= 2:
        return "MEDIUM"
    return "LOW"


def apply_speculation_ceiling(confidence, speculation_level, epistemic_ceiling):
    """운영자 지시 48번: Speculation Level HIGH + Epistemic Ceiling LOW인 경우 confidence는
    LOW를 초과할 수 없다(권장 guard를 강제로 적용)."""
    if speculation_level not in SPECULATION_LEVELS:
        speculation_level = "LOW"
    if speculation_level == "HIGH" and epistemic_ceiling == "LOW":
        return "LOW"
    return confidence
