# EVIDENCE INTERPRETATION(운영자 지시 섹션 4-B, 12~21). "이 Claim이 어떤 구조적 의미를
# 가질 수 있는가" — Claim Content 자체와 절대 하나로 합치지 않는다(claim_extractor.py와
# 파일 자체가 분리되어 있음). 여기서 만드는 모든 객체는 CANDIDATE일 뿐이며, 어떤 규칙도
# CAUSES/CONTROL/POWER_GAIN/BOTTLENECK을 자동 확정하지 않는다(20개 금지 6~9번).
#
# 입력은 claim_extractor.py가 만든 CLAIM(구조화된 subject/predicate/object)이지, 원문
# 텍스트 재스캔이 아니다 — 다만 Scarcity/Bottleneck/Driver 판정에 필요한 명시적 제약
# 언어는 claim.object(=제목 텍스트)에서 규칙으로만 찾는다(섹션 12~18의 "명시적 근거 필요"
# 요건을 코드로 강제하기 위함 — 토픽 키워드 하나만으로는 생성하지 않는다).
import re

from schema import new_evidence_record_shell, FIVE_D_TARGET_TYPES

_RESOURCE_KEYWORDS = {
    "ELECTRICITY": r"전력|전기|electricity|power grid|grid\b",
    "WATER": r"\b물\b|용수|water\b",
    "COMPUTE": r"컴퓨트|연산\s?자원|compute\b|gpu|칩|chip",
    "TALENT": r"인재|인력난|talent\b",
    "DATA": r"데이터\b(?!센터)|\bdata\b(?! center)",
}
_SCARCITY_LANG = re.compile(r"부족|공급\s?부족|품귀|경쟁\s?심화|shortage|scarce|scarcity|supply\s?constraint")
_BOTTLENECK_LANG = re.compile(r"병목|제약|확장\s?(제한|어려움)|한계에?\s?직면|bottleneck|constrain(?:s|ed|t)?|caps?\s?growth")
_DEPENDENCY_LANG = re.compile(r"의존|의존도|에\s?기대|relies?\s+on|depends?\s+on|reliant\s+on")
_CONTROL_LANG = re.compile(r"독점|통제|게이트키핑|접근을?\s?제한|controls?\s+access|gatekeep")
# 사람 검토(섹션 25 Human Review Pilot)에서 발견: "조원/억 달러"는 투자·매출·손해배상 등
# 온갖 금액 표현에 다 쓰여 VALUE_SHIFT를 과다생성했다(예: 단순 투자 발표를 "기업가치 변동"으로
# 오분류). 명시적 가치평가/시가총액 어휘만 남긴다(정확도 우선, 금액 언급 전체 금지).
_VALUE_LANG = re.compile(r"가치평가|기업가치|시가총액|밸류에이션|valuation|market\s?cap")
_DRIVER_RELATION_LANG = [
    ("ACCELERATES", r"가속화|앞당|accelerat"),
    ("SLOWS", r"둔화|지연|slows?|delay"),
    ("CONSTRAINS", r"저해|제약|constrain"),
    ("ENABLES", r"촉진|가능하게|enable"),
]

_CULTURE_ARTS_HINTS = re.compile(r"저작권|박물관|미술관|예술|창작|음악|영화|museum|copyright|creative|artist|provenance")
_PLANET_RESOURCE_HINTS = re.compile(r"전력|전기|물|탄소|배출|기후|환경|데이터센터|electricity|water|carbon|climate|environment|datacenter|data center")


def _real_actor(claim, entities):
    """DRIVER/DEPENDENCY/CONTROL/VALUE의 '주체'는 claim.subject를 그대로 쓰지 않는다 —
    MEDIA_REPORTED류 claim의 subject는 source_id(매체명)일 뿐 실제 행위자가 아니다.
    진짜 행위자로 믿을 수 있는 것만: 기업 발표의 claiming_organization, 또는 제목에서 뽑은
    canonical entity(조직/인물/제품). 둘 다 없으면 None — 억지로 만들지 않는다."""
    if claim.get("claiming_organization"):
        return claim["claiming_organization"]
    if entities:
        return sorted(entities)[0]
    return None


def _find_resource(text):
    for name, pat in _RESOURCE_KEYWORDS.items():
        if re.search(pat, text, re.I):
            return name
    return None


def _domain_hint(claim, document):
    """실제 lineage로 확인 안 되면 UNKNOWN(빈 리스트) — 추측 승격 금지(섹션 19)."""
    text = (claim.get("object") or "") + " " + (document.get("title") or "")
    domains = []
    if document.get("document_type") in ("POLICY", "LAW", "COURT"):
        domains.append("POLICY_LAW_GOVERNANCE")
    if document.get("document_type") == "RESEARCH":
        domains.append("SCIENCE_RESEARCH")
    if _CULTURE_ARTS_HINTS.search(text):
        domains.append("CULTURE_ARTS_MEDIA")
    if _PLANET_RESOURCE_HINTS.search(text):
        domains.append("PLANET")
    if claim.get("claim_type") == "COMPANY_REPORTED":
        domains.append("ECONOMY_INDUSTRY_LABOR")
    return sorted(set(domains)) or []


def _base_record(rid, claim, document, evidence_type, subject, relation, obj, method):
    shell = new_evidence_record_shell(rid, document.get("source_id"), document["document_id"], claim["claim_id"])
    shell.update({
        "evidence_type": evidence_type, "subject": subject, "relation": relation, "object": obj,
        "claim_type": claim.get("claim_type"), "source_type": None,
        "support_type": "ASSOCIATED",  # 규칙으로 찾은 연관성 — DIRECT_SUPPORT로 과대 승격 안 함
        "evidence_strength": "LOW", "epistemic_status": claim.get("claim_status", "NOT_VERIFIED"),
        "interpretation_status": "CANDIDATE", "extraction_method": claim.get("extraction_method"),
        "interpretation_method": method,
        "human_review_status": "PENDING",
        "domains": _domain_hint(claim, document),
        "first_seen": document.get("published"), "last_seen": document.get("published"),
    })
    return shell


def generate_interpretation_candidates(claim, document, entities, now_iso, rid_seq):
    """claim 하나에서 나올 수 있는 Interpretation Candidate 0개 이상을 만든다. 토픽 키워드
    하나만으로는 절대 생성 안 함 — 제약/의존/통제/가치 각각 명시적 언어 트리거가 필요하다."""
    text = f"{claim.get('object') or ''} {document.get('title') or ''}"
    actor = _real_actor(claim, entities)
    out = []

    resource = _find_resource(text)
    if resource and _SCARCITY_LANG.search(text):
        rid = f"evr_{next(rid_seq)}"
        rec = _base_record(rid, claim, document, "SCARCITY_SHIFT", None, "SCARCITY_OF", resource, "RULE_MAPPING")
        rec.update({"resources": [resource]})
        rec["_type_specific"] = {"from_scarcity": None, "to_scarcity": resource,
                                  "mechanism": "명시적 부족/공급제약 언어 매칭"}
        out.append(rec)

    # 섹션 17/18: Scarcity != Bottleneck — Bottleneck은 "시스템 확장을 실제로 제약한다"는
    # 별도 언어(affected_system 함의)가 있어야 하며, Scarcity 매칭과 별개로 판정한다.
    if resource and _BOTTLENECK_LANG.search(text):
        rid = f"evr_{next(rid_seq)}"
        affected_system = "AI_INFRASTRUCTURE" if resource in ("ELECTRICITY", "WATER", "COMPUTE") else "UNKNOWN_SYSTEM"
        rec = _base_record(rid, claim, document, "BOTTLENECK", resource, "CONSTRAINS_EXPANSION_OF", affected_system, "RULE_MAPPING")
        rec.update({"resources": [resource]})
        rec["_type_specific"] = {"resource_or_gate": resource, "affected_system": affected_system,
                                  "controller_if_known": None, "dependency_ids": []}
        out.append(rec)

    m = _DEPENDENCY_LANG.search(text)
    if m and actor:
        rid = f"evr_{next(rid_seq)}"
        target = resource or "UNKNOWN_TARGET"
        rec = _base_record(rid, claim, document, "DEPENDENCY", actor, "DEPENDS_ON", target, "RULE_MAPPING")
        rec["_type_specific"] = {"dependent_actor": actor, "dependency_target": target,
                                  "dependency_function": "명시적 의존 언어 매칭", "dependency_type": resource or "OTHER",
                                  "strength": "LOW", "direction": "UNIDIRECTIONAL"}
        out.append(rec)

    m = _CONTROL_LANG.search(text)
    if m and actor:
        rid = f"evr_{next(rid_seq)}"
        rec = _base_record(rid, claim, document, "CONTROL", actor, "CONTROLS", resource or "UNKNOWN_RESOURCE", "RULE_MAPPING")
        rec["_type_specific"] = {"controller": actor, "controlled_resource_or_access": resource or "UNKNOWN_RESOURCE",
                                  "control_mechanism": "명시적 통제/독점 언어 매칭", "affected_actors": []}
        out.append(rec)

    if _VALUE_LANG.search(text) and actor:
        rid = f"evr_{next(rid_seq)}"
        rec = _base_record(rid, claim, document, "VALUE_SHIFT", actor, "VALUATION_CHANGE", None, "RULE_MAPPING")
        rec["_type_specific"] = {"value_object": actor, "direction": "UNKNOWN",
                                  "value_type": "ECONOMIC", "mechanism": "명시적 가치평가/투자 금액 언어 매칭"}
        out.append(rec)

    for rel_type, pat in _DRIVER_RELATION_LANG:
        if re.search(pat, text, re.I) and actor:
            rid = f"evr_{next(rid_seq)}"
            rec = _base_record(rid, claim, document, "DRIVER", actor, rel_type, None, "RULE_MAPPING")
            rec["_type_specific"] = {"name": actor, "driver_type": document.get("document_type") or "OTHER",
                                      "relation_type": rel_type}
            out.append(rec)
            break  # Driver relation은 문서당 하나만(가장 먼저 매치된 것) — 과다 생성 방지

    for rec in out:
        rec["entities"] = sorted(entities or [])
        rec["created_at"] = now_iso
        rec["updated_at"] = now_iso
    return out
