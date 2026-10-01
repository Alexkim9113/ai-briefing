# N-0 SLICE 1 -- METAXIS_POINT_GROUNDING_GATE. Checks each METAXIS POINT claim sentence against
# real connected evidence before allowing it to publish. Never approves a claim because it
# "sounds plausible" -- only a real, named evidence/claim/intelligence-object connection counts.
GROUNDING_STATUSES = (
    "SOURCE_SUPPORTED", "EVIDENCE_NETWORK_SUPPORTED", "INTELLIGENCE_OBJECT_SUPPORTED",
    "UNSUPPORTED_INTERPRETATION",
)

# Causal/attribution trigger phrases a METAXIS POINT sentence must not use unless grounded.
# This is not an exhaustive NLP causality detector -- it is a conservative, documented list of
# the exact pattern Te's examples show (an unsupported "X 때문에/증가가 Y를 만들고 있다"-style
# causal leap). A sentence containing none of these is never blocked by this specific check (it
# may still be blocked by other grounding requirements upstream).
_CAUSAL_MARKERS = (
    "때문에", "으로 인해", "로 인해", "원인", "초래", "만들고 있다", "주범", "driving",
    "is causing", "due to ai", "because of ai",
)


def _has_causal_claim(sentence):
    s = (sentence or "").lower()
    return any(m.lower() in s for m in _CAUSAL_MARKERS)


def check_point_grounding(sentence, source_document_evidence=None, evidence_network_refs=None,
                           intelligence_object_refs=None):
    """source_document_evidence: True if the sentence's content is directly stated in the
    article itself (not inferred). evidence_network_refs / intelligence_object_refs: lists of
    real connected ids (claim_id/relation_id/intelligence_id) -- empty/None means none exist.
    A causal claim with no real connection of any kind is UNSUPPORTED_INTERPRETATION regardless
    of how plausible it reads."""
    if source_document_evidence:
        return {"status": "SOURCE_SUPPORTED", "reason": "원문에 명시된 내용"}
    if evidence_network_refs:
        return {"status": "EVIDENCE_NETWORK_SUPPORTED", "reason": f"연결된 증거 {len(evidence_network_refs)}건"}
    if intelligence_object_refs:
        return {"status": "INTELLIGENCE_OBJECT_SUPPORTED",
                "reason": f"연결된 Intelligence Object {len(intelligence_object_refs)}건"}
    if _has_causal_claim(sentence):
        return {"status": "UNSUPPORTED_INTERPRETATION",
                "reason": "원문/증거망/Intelligence Object 어디에도 근거가 없는 인과 주장"}
    return {"status": "UNSUPPORTED_INTERPRETATION",
            "reason": "근거가 연결되지 않은 해석 -- 공개 불가"}


def filter_publishable_points(sentences_with_grounding):
    """sentences_with_grounding: list of (sentence, grounding_result). Returns only the
    sentences whose grounding status is NOT UNSUPPORTED_INTERPRETATION -- never silently
    rewrites an unsupported sentence into a supported-sounding one, only drops it."""
    return [s for s, g in sentences_with_grounding if g["status"] != "UNSUPPORTED_INTERPRETATION"]
