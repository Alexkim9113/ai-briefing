# STAGE 7 PHASE A — Intent Classifier. 섹션 3(CODE BEFORE AI), 13(deterministic foundation
# 우선, 애매하면 UNKNOWN/GENERAL_SYNTHESIS 허용): LLM을 쓰지 않는다 - 순수 키워드/패턴 매칭.
# 이 분류가 틀려도 fallback이 GENERAL_SYNTHESIS라 시스템이 깨지지 않는다(fail-soft).
from schema import QUERY_INTENTS

# 표면형은 최소한만 등록한다(Stage 6 concept_registry와 동일 원칙: 자동 확장 없음, 사람이
# 명시적으로 이 표를 넓혀야 한다). 순서가 우선순위 - 위에서부터 첫 매치를 채택한다.
_INTENT_RULES = [
    ("HYPOTHESIS_TEST", ["가설을 검토", "가설을 검증", "가설이 맞", "test the hypothesis", "가설 테스트"]),
    ("COUNTER_EVIDENCE_SEARCH", ["반박", "반대 증거", "counter evidence", "반증"]),
    ("CONTRADICTION_SEARCH", ["모순", "contradiction", "상충"]),
    ("QUESTION_EXPLORATION", ["새로운 질문", "무엇을 물어야", "what question"]),
    ("UNCERTAINTY_ANALYSIS", ["불확실성", "uncertainty", "확실하지 않"]),
    ("VIEW_REVISION", ["생각이 바뀐", "수정해야 할", "이전에 생각했던", "view revision", "changed its mind"]),
    ("TEMPORAL_COMPARISON", ["예전과 비교", "작년과 비교", "시간에 따라", "compared to last"]),
    ("RESEARCH_GAP", ["연구 공백", "아직 밝혀지지 않은", "research gap", "무엇이 알려지지 않았"]),
    ("POLICY_EXPLORATION", ["정책", "규제 방안", "법안", "policy option", "regulation option"]),
    ("FUTURES_EXPLORATION", ["미래에", "앞으로 어떻게 될", "가능한 미래", "미래 경로", "scenario"]),
    ("STRUCTURAL_ANALYSIS", ["구조적으로", "구조 변화", "권한 구조", "structural change"]),
    ("CONNECTION_DISCOVERY", ["연결되는", "연결이 있는", "관련 evidence가 있는가", "연결해줘", "연결"]),
    ("TREND_ANALYSIS", ["추세", "트렌드", "trend", "동향은"]),
    ("CHANGE_ANALYSIS", ["무엇이 달라지고", "무엇이 변화", "what changed", "달라지고 있어"]),
    ("EVENT_LOOKUP", ["사건", "이벤트", "event", "무슨 일이"]),
    ("FACT_LOOKUP", ["사실은", "찾아줘", "언제", "누가", "fact lookup", "무엇인가"]),
]


def classify_intent(normalized_text):
    """정확히 한 규칙만 채택한다(우선순위 순서). 아무 것도 매치하지 않으면 UNKNOWN을
    반환한다 - 스펙 섹션 13이 명시적으로 허용하는 결과이며 GENERAL_SYNTHESIS로 대체하는
    것은 retrieval_planner의 몫이지 classifier가 임의로 승격하지 않는다."""
    for intent, keywords in _INTENT_RULES:
        for kw in keywords:
            if kw in normalized_text:
                assert intent in QUERY_INTENTS
                return intent
    return "UNKNOWN"
