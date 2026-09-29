# PHASE 4B — Canonical Event Name(운영자 지시 15번). 외부 기사 제목을 그대로 복제하지 않고
# ENTITY + ACTION/OBJECT 중심의 짧은 구조적 이름을 규칙으로만 생성. LLM 금지.
_ACTION_LABEL_KO = {
    "RELEASE": "출시", "WITHDRAW": "출시 철회", "ANNOUNCE": "발표", "PARTNER": "파트너십",
    "INVEST": "투자 유치", "ACQUIRE": "인수", "REGULATE": "규제", "SUE": "소송", "RULE": "판결",
    "MEET": "회동", "WARN": "경고", "PUBLISH": "연구 발표", "BAN": "금지", "APPROVE": "승인",
    "INVESTIGATE": "조사", "OTHER": "동향",
}


def canonical_event_name(entities, action_family, distinctive_terms):
    label = _ACTION_LABEL_KO.get(action_family, "동향")
    ents = list(entities)[:2]
    terms = [t for t in distinctive_terms if t not in ents][:1]
    if len(ents) >= 2:
        base = f"{ents[0]}-{ents[1]} {label}"
    elif len(ents) == 1:
        base = f"{ents[0]} {label}"
    else:
        base = label
    if terms:
        base += f" ({terms[0]})"
    return base[:80]
