# STAGE 7 PHASE H — Two-Pass Deep Think. 섹션 46(원 스펙) + Te CONTINUE 섹션 12: PASS 1은
# 23개 항목의 ANALYTICAL CONSTRUCTION, 그 다음에만 PASS 2 SYNTHESIS. 문장이 사고를
# 대신하지 않는다 - Pass 1이 구조를 만들고 Pass 2가 그 구조를 문장으로 옮긴다.
import json

import claude_adapter
from epistemic_guard import anti_generic_insight_test, check_claim_ceiling
from prompt_contract import PROMPT_VERSION, SYSTEM_PROMPT_TEMPLATE, model_for_mode

# Te CONTINUE 섹션 12 순서 그대로 - 새 순서를 발명하지 않는다.
PASS1_FIELDS = (
    "question", "scope", "evidence_map", "what_happened", "what_changed",
    "what_did_not_change", "anomaly", "contradictions", "counter_evidence",
    "alternative_explanations", "new_connections", "possible_mechanisms",
    "relevant_disciplinary_lenses", "structural_interpretation_if_justified",
    "intellectual_novelty_check", "existing_view_collision_check",
    "second_third_order_effects_if_justified", "futures_paths_if_justified",
    "reality_return", "falsifiers", "monitoring_indicators",
    "claim_ceiling", "interpretation_ceiling",
)

_PASS1_INSTRUCTIONS = """Below is the METAXIS Context Pack for an operator's Deep Think question. \
Perform PASS 1 — ANALYTICAL CONSTRUCTION only. Do not write prose yet. Return a JSON object \
with exactly these keys, each a short bullet list (empty list if evidence does not support that \
item — an empty "contradictions" or "counter_evidence" list is a normal, honest result, not a \
failure): {fields}

Evidence-first framework selection (do not force POWER/SCARCITY/AUTONOMY/etc onto every \
question): ask what actually happened, what changed, what did not, what is strange, what the \
existing explanation fails to explain, whether there is a contradiction or unexpected \
connection, and only then which discipline is actually useful.

CONTEXT PACK:
{context_pack_json}

QUESTION: {question}
"""

_PASS2_INSTRUCTIONS = """Using ONLY the PASS 1 analytical construction below (do not add facts or \
connections that are not already in it), write the operator-facing SYNTHESIS. Keep it to clear \
thinking and precise expression (this is Stage 7, not Stage 8 editorial writing — no literary \
polish, no forced use of internal vocabulary like "scarcity shift" as a sentence, say what it \
actually means in plain language). Do not exceed the claim_ceiling or interpretation_ceiling \
given in PASS 1. If PASS 1's contradictions/counter_evidence/anomaly lists are empty, say so \
plainly rather than inventing tension.

PASS 1:
{pass1_json}
"""


def run_pass1(context_pack, question, evidence_sufficiency, client_factory=None):
    model = model_for_mode("DEEP_THINK")
    system = SYSTEM_PROMPT_TEMPLATE.format(
        claim_ceiling=evidence_sufficiency.get("claim_ceiling"),
        evidence_sufficiency=evidence_sufficiency.get("state"))
    user = _PASS1_INSTRUCTIONS.format(
        fields=list(PASS1_FIELDS),
        context_pack_json=json.dumps(context_pack, ensure_ascii=False),
        question=question)
    result = claude_adapter.call_claude(system, user, model, client_factory=client_factory)
    return result


def run_pass2(pass1_result_json, client_factory=None):
    model = model_for_mode("DEEP_THINK")
    user = _PASS2_INSTRUCTIONS.format(pass1_json=pass1_result_json)
    result = claude_adapter.call_claude(SYSTEM_PROMPT_TEMPLATE.format(
        claim_ceiling="see PASS 1", evidence_sufficiency="see PASS 1"), user, model,
        client_factory=client_factory)
    return result


def run_deep_think(context_pack, question, evidence_sufficiency, client_factory=None):
    """섹션 61: Claude 실패 시 전체 실패 금지 - PASS 1이 실패하면 RETRIEVAL_ONLY로 후퇴."""
    pass1 = run_pass1(context_pack, question, evidence_sufficiency, client_factory)
    if pass1["status"] != "CONFIGURED":
        return {"status": "RETRIEVAL_ONLY_FALLBACK", "reason": pass1["status"],
                "pass1": None, "pass2": None, "guard": None}

    pass2 = run_pass2(pass1["text"], client_factory)
    if pass2["status"] != "CONFIGURED":
        return {"status": "PASS1_ONLY_FALLBACK", "reason": pass2["status"],
                "pass1": pass1["text"], "pass2": None, "guard": None}

    used_ids = context_pack.get("object_references", [])
    guard = anti_generic_insight_test(pass2["text"], context_pack, used_ids)
    capped_ceiling, was_capped = check_claim_ceiling(
        evidence_sufficiency.get("claim_ceiling"), evidence_sufficiency.get("claim_ceiling"))

    return {
        "status": "COMPLETE", "pass1": pass1["text"], "pass2": pass2["text"],
        "guard": guard, "claim_ceiling": capped_ceiling, "claim_ceiling_was_capped": was_capped,
        "prompt_version": PROMPT_VERSION, "model": model_for_mode("DEEP_THINK"),
    }
