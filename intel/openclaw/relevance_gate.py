# O-4C — AI + STRUCTURAL RELEVANCE GATE
# Operator-only. This module is intentionally isolated from Public briefing.py/data/site.
#
# Goal:
#   1) DIRECT: the document is explicitly about AI.
#   2) STRUCTURAL: the document is not necessarily about AI, but concerns a variable that can
#      materially constrain, accelerate, regulate, finance, supply, or reshape AI deployment.
#   3) CONTEXT: plausible adjacent signal requiring synthesis/review.
#   4) NONE: no defensible AI relationship from the title/description.
#
# This gate is deliberately conservative. It does NOT claim that every climate/energy/labour
# article is AI intelligence. Structural candidates are routed to NEEDS_REVIEW so the existing
# Gemini synthesis step can explain (or fail to explain) why the item matters. The original
# document is always preserved.

import re

_STRONG_AI_PATTERNS = [
    r"\bAI\b", r"\bA\.I\.\b", r"AI(?=[一-鿿])", r"(?<=[一-鿿])AI",
    r"artificial intelligence", r"generative ai", r"genai", r"large language model",
    r"\bllm\b", r"machine learning", r"deep learning", r"neural network",
    r"\bchatgpt\b", r"\bgemini\b", r"\bclaude\b", r"\bcopilot\b", r"\bagentic\b",
    r"\bai agent\b", r"foundation model", r"\bai chip\b", r"\bai safety\b",
    r"\bai regulation\b", r"ai model",
    "人工智能", "大模型", "生成式人工智能", "深度学习", "机器学习", "AI训练", "AI大模型",
    "AI剧", "AI芯片", "AI安全", "智能体",
    "인공지능", "생성형 ai", "생성형ai", "대규모 언어모델", "거대언어모델", "에이전트형 ai",
    "ai 에이전트", "ai 모델", "ai반도체", "ai 반도체", "ai규제", "ai 규제", "ai저작권",
    "ai 안전", "ai 윤리",
]

# Structural variables that may matter to AI even when the article itself never says "AI".
# Each group carries an explicit causal-path template. A hit is NOT PASS; it is NEEDS_REVIEW.
# The downstream synthesis must still justify the connection using the actual article text.
_STRUCTURAL_GROUPS = {
    "ENERGY_GRID": {
        "patterns": [r"electricity demand", r"power demand", r"power grid", r"electric grid",
                     r"grid connection", r"transmission line", r"substation", r"power shortage",
                     r"nuclear power", r"renewable energy", r"power purchase agreement", r"\bPPA\b",
                     "전력수요", "전력망", "송전망", "계통접속", "변전소", "전력부족", "원자력", "재생에너지",
                     "电力需求", "电网", "输电", "核电", "可再生能源"],
        "causal_path": "에너지·전력망 → 컴퓨팅 공급능력/비용 → AI 인프라 확장",
        "intelligence": "AI × ENERGY",
    },
    "CLIMATE_COOLING": {
        "patterns": [r"heatwave", r"extreme heat", r"record temperature", r"climate change",
                     r"cooling demand", r"water stress", r"drought", r"water shortage",
                     "폭염", "이상고온", "기후변화", "냉방수요", "물부족", "가뭄", "용수",
                     "高温", "热浪", "气候变化", "缺水", "干旱"],
        "causal_path": "기후·물 → 냉각/전력 피크·입지 제약 → AI 데이터센터 비용·가용성",
        "intelligence": "AI × ENERGY / CLIMATE",
    },
    "CHIPS_SUPPLY_CHAIN": {
        "patterns": [r"semiconductor", r"advanced chip", r"chip export", r"export control",
                     r"rare earth", r"critical mineral", r"lithium", r"copper shortage",
                     "반도체", "첨단칩", "수출통제", "희토류", "핵심광물", "리튬", "구리",
                     "半导体", "芯片", "出口管制", "稀土", "关键矿产"],
        "causal_path": "반도체·핵심광물 공급망 → 컴퓨팅 공급/가격 → AI 확산 속도",
        "intelligence": "AI × COMPUTE / SUPPLY CHAIN",
    },
    "LABOR_SKILLS": {
        "patterns": [r"labor market", r"labour market", r"job displacement", r"workforce shortage",
                     r"productivity growth", r"skills shortage", r"reskilling", r"white collar",
                     "노동시장", "일자리 감소", "인력부족", "생산성", "재교육", "숙련", "화이트칼라",
                     "劳动力市场", "就业", "生产率", "技能"],
        "causal_path": "노동·숙련 변화 ↔ 자동화 유인/흡수능력 → AI 도입과 분배효과",
        "intelligence": "AI × LABOR",
    },
    "LAW_IP_DATA": {
        "patterns": [r"\bcopyright\b", r"intellectual property", r"data protection", r"privacy law",
                     r"digital regulation", r"platform regulation", "저작권", "지식재산", "개인정보", "데이터보호",
                     "版权", "著作权", "知识产权", "数据保护", "个人信息"],
        "causal_path": "법·권리·데이터 규칙 → 학습/서비스 허용범위·책임 → AI 시장 구조",
        "intelligence": "AI × LAW / COPYRIGHT",
    },
    "CAPITAL_MARKET": {
        "patterns": [r"data center investment", r"infrastructure investment", r"venture funding",
                     r"capital expenditure", r"\bcapex\b", r"interest rate", r"financing cost",
                     "데이터센터 투자", "인프라 투자", "벤처투자", "설비투자", "금리", "자금조달",
                     "数据中心投资", "基础设施投资", "融资", "利率"],
        "causal_path": "자본비용·투자 → 데이터센터/컴퓨팅 증설 → AI 공급과 산업집중",
        "intelligence": "AI × ECONOMY / CAPITAL",
    },
    "GEOPOLITICS_SECURITY": {
        "patterns": [r"technology sanctions", r"trade restriction", r"industrial policy",
                     r"strategic competition", r"national security technology", r"digital sovereignty",
                     "기술제재", "무역제한", "산업정책", "기술패권", "경제안보", "디지털주권",
                     "技术制裁", "产业政策", "国家安全", "数字主权"],
        "causal_path": "지정학·산업정책 → 기술/자본/칩 접근성 → AI 역량의 국가별 분화",
        "intelligence": "AI × GEOPOLITICS",
    },
}

_CONTEXT_PATTERNS = [
    r"\baccess token", r"\bidentity\b.*\btoken", "신원", "접근 토큰",
    r"\balgorithm", r"\bautomat(ed|ion)\b", r"\brobot", r"\bbiometric",
    "알고리즘", "자동화", "로봇", "생체인식", "算法", "自动化", "机器人",
]


def _contains_any(text, patterns):
    if not text:
        return []
    hits = []
    for p in patterns:
        try:
            if re.search(p, text, re.IGNORECASE):
                hits.append(p)
        except re.error:
            if p in text:
                hits.append(p)
    return hits


def classify(original_title, raw_description=""):
    """Classify relevance from real title/description only.

    Returns the legacy status field for compatibility plus richer relation metadata used by
    Operator/intelligence synthesis. DIRECT is PASS. STRUCTURAL/CONTEXT are NEEDS_REVIEW.
    NONE is FAIL. No source prestige can upgrade a verdict.
    """
    text = f"{original_title or ''} {raw_description or ''}"
    strong_hits = _contains_any(text, _STRONG_AI_PATTERNS)
    if strong_hits:
        return {
            "status": "PASS",
            "relation_type": "DIRECT",
            "matched_keywords": strong_hits[:5],
            "structural_axis": None,
            "causal_path": "문서 자체가 AI를 직접 다룸",
            "linked_intelligence": [],
            "reason": "제목/설명에 AI 핵심 신호가 직접 등장함",
        }

    structural_matches = []
    for axis, cfg in _STRUCTURAL_GROUPS.items():
        hits = _contains_any(text, cfg["patterns"])
        if hits:
            structural_matches.append((axis, cfg, hits))
    if structural_matches:
        axis, cfg, hits = structural_matches[0]
        return {
            "status": "NEEDS_REVIEW",
            "relation_type": "STRUCTURAL",
            "matched_keywords": hits[:5],
            "structural_axis": axis,
            "causal_path": cfg["causal_path"],
            "linked_intelligence": [cfg["intelligence"]],
            "reason": "AI 직접 기사는 아니지만 AI의 비용·인프라·확산·규제·시장구조를 바꿀 수 있는 구조적 변수. 실제 인과 연결은 synthesis에서 검증해야 함",
        }

    context_hits = _contains_any(text, _CONTEXT_PATTERNS)
    if context_hits:
        return {
            "status": "NEEDS_REVIEW",
            "relation_type": "CONTEXT",
            "matched_keywords": context_hits[:5],
            "structural_axis": None,
            "causal_path": None,
            "linked_intelligence": [],
            "reason": "AI와 연결될 가능성이 있으나 현재 텍스트만으로 구조적 인과경로가 충분히 특정되지 않음",
        }

    return {
        "status": "FAIL",
        "relation_type": "NONE",
        "matched_keywords": [],
        "structural_axis": None,
        "causal_path": None,
        "linked_intelligence": [],
        "reason": "현재 제목/설명만으로 AI와의 직접 또는 구조적 관계를 설명할 근거가 없음",
    }


def source_tier(source_type):
    return {
        "PRIMARY": "TIER1_PRIMARY",
        "RESEARCH": "TIER1_RESEARCH",
        "NEWS": "TIER2_NEWS",
    }.get(source_type, "TIER3_UNVERIFIED")
