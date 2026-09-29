# PHASE 4A EVENT MATCHING PILOT — Pairwise Candidate Signals. Shadow/실험 전용:
# 이 모듈은 어디에서도 기존 briefing.py/site/에 연결되지 않는다(운영자 지시 19).
#
# Entity/Distinctive-term 추출은 새 사전을 만들지 않고 기존 briefing.py의 KW_GROUPS/
# mx_keywords를 그대로 재사용한다(운영자 지시 2번: "거대한 수동 기업 사전을 만들지 마세요").
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "intel"))
import briefing  # noqa: E402 — 함수만 재사용, 이 파일에서 절대 수정하지 않음
from evidence_service import extract_identifiers  # noqa: E402

# ---------------------------------------------------------------- Entity normalization
# 운영자 예시(OpenAI/오픈AI/오픈에이아이 → OPENAI, NVIDIA/Nvidia/엔비디아 → NVIDIA)는
# briefing.KW_GROUPS/_KW_CANON에 이미 구조적으로 들어 있다 — 새로 만들지 않고 그대로 쓴다.
_ENTITY_GROUPS = set(range(len(briefing.KW_GROUPS)))  # 조직/인물/제품 계열만 쓰고 "규제"/"정책" 같은 topic성 그룹은 제외
_TOPIC_LIKE_GROUP_NAMES = {"규제", "정책", "생성형", "LLM", "에이전트", "보안", "교육", "의료", "투자",
                           "스타트업", "일자리", "금융", "국방", "자율주행", "클라우드", "저작권",
                           "반도체", "로봇", "데이터센터", "인공지능", "CEO", "중국"}


def canonical_entities(item):
    """조직/인물/제품 계열 canonical 이름 집합만 뽑는다(국가/일반 topic성 그룹은 제외).
    briefing.item_tags는 최대 3개만 반환하므로, 전체 KW_GROUPS를 직접 스캔해 빠짐없이 모은다."""
    title = (item.get("title", "") + " " + (item.get("title_ko") or "")).lower()
    out = set()
    for i, name, rx in briefing._TAG_RX:
        if name in _TOPIC_LIKE_GROUP_NAMES:
            continue
        if rx.search(title):
            out.add(name)
    return out


# mx_keywords()는 일반 AI 낱말 상당수를 걸러내지만, "모델"/"기술"/"서비스"처럼 기사마다
# 반복되는 낱말 일부는 통과시킨다(발견한 문제) — 운영자 지시 4번대로 이런 낱말은 낮은
# weight/stopword로 추가 처리한다. 새 사전이 아니라 mx_keywords 출력에 대한 얇은 후처리.
_GENERIC_AI_TERMS = {"모델", "기술", "서비스", "시스템", "기업", "산업", "데이터", "인공지능", "플랫폼",
                     "model", "technology", "service", "system", "company", "industry", "data", "platform"}


# ---------------------------------------------------------------- Distinctive terms
def distinctive_terms(item):
    """mx_keywords()는 이미 일반 AI 낱말·조사·수식어를 걸러내고 명사 핵심어만 남긴다 —
    새 stopword 로직을 또 만들지 않고 그대로 재사용하되, 그래도 새는 초일반 낱말만 얇게 더 거른다."""
    try:
        return {w for w in briefing.mx_keywords(item, n=6) if w.lower() not in _GENERIC_AI_TERMS}
    except Exception:
        return set()


# ---------------------------------------------------------------- Action family
# LLM 없이 Keyword/Rule 기반(운영자 지시 5번). briefing._EVENTS와는 별개 — _EVENTS는
# "주제+행위"가 섞여 있어 순수 행위(action) 판별에는 너무 거칠다.
ACTION_FAMILIES = [
    # 취소·보류(WITHDRAW)는 RELEASE와 정반대 행위라서, RELEASE보다 먼저 검사해 "출시 철회"가
    # RELEASE로 잘못 분류되는 걸 막는다(오탐 발견: OpenAI 모델 출시 철회 vs Anthropic 모델 출시).
    ("WITHDRAW", r"철회|보류|중단|철수|scraps?\b|abandons?\b|halts?\b|pulls? back|withdraws?\b|scrapped"),
    # "기업공개"(IPO)는 "공개"를 포함하지만 RELEASE가 아니므로 제외(부정 lookbehind)
    ("RELEASE", r"출시|(?<!기업)공개|선보|론칭|배포|release[sd]?\b|launch(?:e[sd])?|unveil|roll(?:s|ed)? out|debut"),
    ("ANNOUNCE", r"발표|밝혔|밝혀|공표|announc"),
    ("PARTNER", r"협력|제휴|협약|파트너|partner|team(?:s|ed)? up|collaborat"),
    ("INVEST", r"투자|유치|펀딩|invest|funding|raise[sd]?\b|valuation"),
    ("ACQUIRE", r"인수|합병|acqui|merger|takeover"),
    ("REGULATE", r"규제|금지법|입법|법안|규정|regulat|bill\b(?!ion)|legislat"),
    ("SUE", r"소송|고소|제소|피소|sues?\b|lawsuit|files? suit"),
    ("RULE", r"판결|재판부|선고|ruling|rules? (?:that|in)|court (?:says|finds)|judge"),
    ("MEET", r"회동|만찬|면담|단독 만남|meets?\b|dinner|meetings?\b"),
    ("WARN", r"경고|우려|위협|촉구|warn|threat|urg(?:e|es|ed)"),
    ("PUBLISH", r"논문|연구 결과|공개했|게재|publish(?:es|ed)?\b|paper\b"),
    ("BAN", r"금지|차단|banned?\b|blocks?\b"),
    ("APPROVE", r"승인|허가|approve[sd]?\b|greenlight"),
    ("INVESTIGATE", r"조사|수사|심리|inquiry|investigat|probe"),
]
ACTION_FAMILIES = [(name, re.compile(rx, re.I)) for name, rx in ACTION_FAMILIES]


def action_family(item):
    """제목에서 첫 번째로 매치되는 action family 하나만 뽑는다(가볍게, 여러 개 조합 안 함)."""
    title = item.get("title", "") + " " + (item.get("title_ko") or "")
    for name, rx in ACTION_FAMILIES:
        if rx.search(title):
            return name
    return "OTHER"


# ---------------------------------------------------------------- Basic helpers
def title_similarity(a, b):
    ga = briefing.grams(briefing.title_key(a.get("title_ko") or a["title"]))
    gb = briefing.grams(briefing.title_key(b.get("title_ko") or b["title"]))
    if not ga[0] or not gb[0]:
        return 0.0
    return len(ga[0] & gb[0]) / len(ga[0] | gb[0])


def date_distance_days(a, b):
    from datetime import datetime
    def d(it):
        p = it.get("published")
        if not p:
            return None
        try:
            return datetime.fromisoformat(p.replace("Z", "+00:00")).date()
        except Exception:
            return None
    da, db = d(a), d(b)
    if da is None or db is None:
        return None
    return abs((da - db).days)


def identifier_match(a, b):
    """DOI/arXiv ID가 둘 다 있고 같은 논문을 가리키면 매우 강한 신호. evidence_service의
    normalize 로직을 그대로 재사용(새 정규화 규칙을 또 안 만듦)."""
    ida = {norm["normalized"] for _, norm in extract_identifiers((a.get("title", "") + " " + (a.get("summary") or "")))}
    idb = {norm["normalized"] for _, norm in extract_identifiers((b.get("title", "") + " " + (b.get("summary") or "")))}
    if not ida or not idb:
        return None  # 판단 불가(정보 없음) — MATCH도 MISMATCH도 아님
    return bool(ida & idb)


def document_type_of(item):
    """이번 Pilot은 document_service의 _guess_document_type을 그대로 재사용하되, 원본
    도메인 정보 없이 category만으로 빠르게 근사한다(RESEARCH/NEWS/POLICY만 구분하면 충분)."""
    cat = item.get("category")
    if cat == "papers":
        return "RESEARCH"
    if cat == "policy":
        return "POLICY"
    if cat == "talks":
        return "VIDEO"
    return "NEWS"


def document_type_compatible(a, b):
    ta, tb = document_type_of(a), document_type_of(b)
    if ta == tb:
        return True
    # NEWS가 POLICY/RESEARCH를 취재한 기사일 수 있어 완전히 배타적이진 않음(약한 비호환)
    return {ta, tb} in ({"NEWS", "POLICY"},)


def topic_compatible(a, b):
    try:
        ta, _ = briefing.topic_of(a)
        tb, _ = briefing.topic_of(b)
        return ta == tb and ta is not None
    except Exception:
        return False


def compute_signals(a, b):
    """Document A/B 쌍에 대한 모든 Pairwise Signal(운영자 지시 3번)을 계산한다.
    source_diversity는 의도적으로 여기 없음(운영자 지시: pair 판정 신호로 안 씀, 12번 참고)."""
    ent_a, ent_b = canonical_entities(a), canonical_entities(b)
    term_a, term_b = distinctive_terms(a), distinctive_terms(b)
    act_a, act_b = action_family(a), action_family(b)
    return {
        "exact_identifier_match": identifier_match(a, b),
        "canonical_entity_overlap": sorted(ent_a & ent_b),
        "entity_union_size": len(ent_a | ent_b),
        "event_date_distance_days": date_distance_days(a, b),
        "title_similarity": round(title_similarity(a, b), 3),
        "distinctive_term_overlap": sorted(term_a & term_b),
        "action_family_a": act_a, "action_family_b": act_b,
        "action_compatible": (act_a == act_b) if (act_a != "OTHER" and act_b != "OTHER") else None,
        "document_type_compatible": document_type_compatible(a, b),
        "topic_compatible": topic_compatible(a, b),
    }
