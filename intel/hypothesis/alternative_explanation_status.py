# N-0 SLICE 4/8 -- Alternative Explanation Evidence status. Each alternative explanation on a
# Hypothesis must resolve to either a real ALTERNATIVE_EXPLANATION -> EVIDENCE -> CLAIM -> RELATION
# chain, or stay UNSUPPORTED_ALTERNATIVE -- never silently assumed true or false.
ALTERNATIVE_EXPLANATION_STATUSES = ("EVIDENCE_CONNECTED", "UNSUPPORTED_ALTERNATIVE")


def new_alternative_explanation_record(hypothesis_id, explanation, evidence_ids=None):
    evidence_ids = evidence_ids or []
    status = "EVIDENCE_CONNECTED" if evidence_ids else "UNSUPPORTED_ALTERNATIVE"
    return {
        "hypothesis_id": hypothesis_id, "explanation": explanation, "evidence_ids": evidence_ids,
        "status": status,
    }
