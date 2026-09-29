# SOURCE INTELLIGENCE CORRECTION v1.0 — Phase J(spec 섹션 38/65). 가벼운 curated entity
# resolution. 거대 ontology나 LLM 대량 alias 생성 금지(섹션 38 마지막) - evidence_supply/
# source_registry.py의 ALIAS_BASIS 원칙(EXACT/DOMAIN_VERIFIED/KNOWN_ALIAS/HUMAN_CONFIRMED)
# 과 동일한 정신으로, 사람이 확인한 것만 등록한다.
ENTITY_TYPES = ("ORGANIZATION", "PERSON", "TECHNOLOGY", "MODEL", "POLICY", "LAW",
                "INSTITUTION", "COUNTRY", "JURISDICTION")

# 이 세션에서 실제로 검증 가능한, 반복적으로 등장하는 것만 최소 시드로 넣는다(섹션 42와
# 동일 원칙 - 전 세계 기관을 미리 나열하지 않는다).
_SEED_ENTITIES = (
    {"entity_id": "org_openai", "canonical_name": "OpenAI", "entity_type": "ORGANIZATION",
     "aliases": ["Open AI", "오픈AI", "오픈에이아이"]},
    {"entity_id": "org_anthropic", "canonical_name": "Anthropic", "entity_type": "ORGANIZATION",
     "aliases": ["앤트로픽", "안트로픽"]},
    {"entity_id": "org_google_deepmind", "canonical_name": "Google DeepMind", "entity_type": "ORGANIZATION",
     "aliases": ["구글 딥마인드", "DeepMind", "딥마인드"]},
    {"entity_id": "org_meta", "canonical_name": "Meta", "entity_type": "ORGANIZATION",
     "aliases": ["메타"]},
    {"entity_id": "policy_eu_ai_act", "canonical_name": "EU AI Act", "entity_type": "POLICY",
     "aliases": ["AI Act", "유럽연합 인공지능법", "EU 인공지능법", "유럽 AI법"]},
    {"entity_id": "tech_llm", "canonical_name": "대규모 언어모델", "entity_type": "TECHNOLOGY",
     "aliases": ["LLM", "large language model", "언어모델"]},
    {"entity_id": "country_us", "canonical_name": "미국", "entity_type": "COUNTRY",
     "aliases": ["US", "U.S.", "美", "United States"]},
    {"entity_id": "country_kr", "canonical_name": "한국", "entity_type": "COUNTRY",
     "aliases": ["韓", "Korea", "South Korea"]},
    {"entity_id": "country_cn", "canonical_name": "중국", "entity_type": "COUNTRY",
     "aliases": ["China", "中", "Chinese"]},
)


def _build_index():
    idx = {}
    for e in _SEED_ENTITIES:
        assert e["entity_type"] in ENTITY_TYPES, f"unknown entity_type: {e['entity_type']}"
        idx[e["canonical_name"].lower()] = e["entity_id"]
        for a in e["aliases"]:
            idx[a.lower()] = e["entity_id"]
    return idx


_INDEX = _build_index()
_BY_ID = {e["entity_id"]: e for e in _SEED_ENTITIES}


def resolve_entity(surface_form):
    """surface_form(원문에 나온 그대로의 표기)을 canonical entity_id로 해석한다.
    등록되지 않은 표기는 추측해서 묶지 않고 None(=미해결)을 반환한다 - 섹션 38:
    "LLM으로 수천 개 alias를 만들지 않는다"와 같은 정신으로, curated 목록 밖은 UNKNOWN."""
    return _INDEX.get((surface_form or "").strip().lower())


def entity_record(entity_id):
    return _BY_ID.get(entity_id)


def resolution_status():
    """섹션 21 audit 재확인용: 현재 이 모듈의 커버리지 수준을 코드가 스스로 보고한다
    (EXISTS/PARTIAL/ABSENT를 사람이 다시 눈대중으로 판단하지 않게)."""
    n = len(_SEED_ENTITIES)
    types_covered = {e["entity_type"] for e in _SEED_ENTITIES}
    return {
        "seed_entity_count": n,
        "entity_types_covered": sorted(types_covered),
        "entity_types_missing": sorted(set(ENTITY_TYPES) - types_covered),
        "status": "PARTIAL" if n > 0 else "ABSENT",
    }
