# PHASE 4B — Event Type Controlled Vocabulary(운영자 지시 6번). Action Family +
# document_type + 최소한의 키워드 규칙으로만 판정. LLM 사용 안 함. 불확실하면 OTHER.
EVENT_TYPES = ("PRODUCT_RELEASE", "MODEL_RELEASE", "RESEARCH_PUBLICATION", "POLICY_ANNOUNCEMENT",
               "LAW_ENACTMENT", "COURT_DECISION", "REGULATORY_ACTION", "COMPANY_ACTION",
               "PARTNERSHIP", "FUNDING", "INFRASTRUCTURE", "SECURITY_INCIDENT", "PUBLIC_STATEMENT",
               "LEGAL_ACTION", "LABOR_CHANGE", "CULTURAL_CHANGE", "ENVIRONMENTAL_IMPACT", "OTHER")

_MODEL_HINTS = ("모델", "gpt", "claude", "sonnet", "gemini", "llama", "model")
_GOV_SOURCE_HINTS = ("행안부", "과기정통부", "정부", "국회", "백악관", "white house", "eu", "european commission",
                     "ministry", "행정안전부", "중기부")


def classify_event_type(action_family, document_type, entities, title, is_gov_actor):
    """운영자 지시 6번(불확실하면 OTHER, 억지 분류 금지) + 지시된 예시(빌 게이츠 발언은
    POLICY_ANNOUNCEMENT가 아니라 PUBLIC_STATEMENT)를 그대로 규칙화."""
    t = (title or "").lower()

    if action_family == "RULE":
        return "COURT_DECISION"
    if action_family == "SUE":
        return "LEGAL_ACTION"
    if action_family == "REGULATE":
        return "LAW_ENACTMENT" if any(k in t for k in ("법안", "bill", "act\b")) else "REGULATORY_ACTION"
    if action_family == "INVESTIGATE" or action_family == "BAN" or action_family == "APPROVE":
        return "REGULATORY_ACTION"
    if action_family == "PARTNER":
        return "PARTNERSHIP"
    if action_family == "INVEST":
        return "FUNDING"
    if action_family == "ACQUIRE":
        return "COMPANY_ACTION"
    if action_family == "PUBLISH" or document_type == "RESEARCH":
        return "RESEARCH_PUBLICATION"
    if action_family in ("RELEASE", "WITHDRAW"):
        if any(h in t for h in _MODEL_HINTS):
            return "MODEL_RELEASE"
        return "PRODUCT_RELEASE"
    if action_family in ("ANNOUNCE", "WARN"):
        # 핵심: 정부/공식기관 발표만 POLICY_ANNOUNCEMENT, 개인·기업의 의견 표명은
        # PUBLIC_STATEMENT(운영자 지시: 빌 게이츠 발언을 POLICY_ANNOUNCEMENT로 분류 금지)
        return "POLICY_ANNOUNCEMENT" if is_gov_actor else "PUBLIC_STATEMENT"
    if action_family == "MEET":
        return "COMPANY_ACTION"
    return "OTHER"


def is_gov_actor(item, source_id=None, domain=None):
    text = (item.get("source", "") + " " + item.get("title", "")).lower()
    return any(h in text for h in _GOV_SOURCE_HINTS)
