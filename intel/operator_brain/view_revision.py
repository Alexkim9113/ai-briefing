# STAGE 7 PHASE G-K CHECKPOINT REMEDIATION (item 3/3) — View Revision Candidate.
# Te 지시: 자동 revision 절대 금지. 항상 사람 승인 전 VIEW_REVISION_CANDIDATE 객체만
# 만든다 - canonical Stage 6 memory(knowledge_memory/notes.json)는 이 모듈 어디에서도
# import되지 않는다(candidate_memory.py와 동일한 격리 원칙). REVISION != CONTRADICTION:
# 약한 반박 증거 하나로 REVERSE를 만들지 않고, source_quality/directness/
# temporal_relevance/scope_match/independence/measurement_quality 6축을 합산한
# materiality_score로만 강한 revision_type을 허용한다.
import hashlib
import json
from pathlib import Path

VIEW_REVISION_PATH = Path(__file__).resolve().parent / "view_revision_candidates.json"

# BOUNDARY_CONDITION은 1급 revision_type이다(Te 지시) - "기존 view가 특정 scope 안에서만
# 맞고 그 밖에서는 다르다"는 발견은 REVERSE/QUALIFY 어느 쪽으로도 정확히 표현되지 않는다.
REVISION_TYPES = (
    "WEAKEN", "NARROW_SCOPE", "EXPAND_SCOPE", "QUALIFY", "PARTIAL_REVISE",
    "REVERSE", "BOUNDARY_CONDITION", "NO_REVISION_NEEDED",
)

TRIGGER_REASONS = (
    "NEW_CONTRADICTING_EVIDENCE", "NEW_COUNTER_EVIDENCE", "SCOPE_MISMATCH_DISCOVERED",
    "TEMPORAL_STALENESS", "INDEPENDENT_REPLICATION_FAILED", "BOUNDARY_CONDITION_FOUND",
    "STRONGER_SOURCE_CONTRADICTS",
)

_RELATIONSHIPS = ("SUPPORTS", "EXTENDS", "QUALIFIES", "WEAKENS", "CONTRADICTS", "REVEALS_BOUNDARY")

# Novelty Gate 연결(Te 지시) - epistemic_guard.NOVELTY_KINDS(범용 후보 어휘)와는 별개의,
# revision 후보 전용 어휘다. 기존 epistemic_guard.assess_novelty()의 NOVELTY_KINDS는
# 건드리지 않는다.
VIEW_REVISION_NOVELTY_KINDS = (
    "SUPPORTING_EVIDENCE_ONLY", "EXTENSION_CANDIDATE",
    "VIEW_REVISION_CANDIDATE", "HIGH_VALUE_VIEW_REVISION_CANDIDATE",
    "NO_NOVELTY",
)

_RELATIONSHIP_TO_NOVELTY = {
    "SUPPORTS": "NO_NOVELTY",
    "EXTENDS": "EXTENSION_CANDIDATE",
    "QUALIFIES": "VIEW_REVISION_CANDIDATE",
    "WEAKENS": "VIEW_REVISION_CANDIDATE",
    "CONTRADICTS": "HIGH_VALUE_VIEW_REVISION_CANDIDATE",
    "REVEALS_BOUNDARY": "HIGH_VALUE_VIEW_REVISION_CANDIDATE",
}

_QUALITY_SCORE = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "UNKNOWN": 0}
_QUALITY_DIMS = ("source_quality", "directness", "temporal_relevance", "scope_match",
                  "independence", "measurement_quality")

# REVERSE != 단일 약한 반박(섹션 17 Te 지시). 문턱을 넘어야만 강한 revision_type을 허용.
_REVERSE_MATERIALITY_THRESHOLD = 10  # 6축 중 대부분이 HIGH(3점)에 가까워야 도달
_QUALIFY_MATERIALITY_THRESHOLD = 4


def novelty_kind_for_relationship(relationship):
    assert relationship in _RELATIONSHIPS, f"unknown relationship: {relationship}"
    return _RELATIONSHIP_TO_NOVELTY[relationship]


def compute_materiality(quality_comparison):
    """quality_comparison: {dim: HIGH/MEDIUM/LOW/UNKNOWN, ...} - 새 evidence가 기존
    view의 근거보다 그 축에서 얼마나 더 강한지. 한 축만 강하다고 전체를 강한 revision으로
    만들지 않는다 - 6축 합산 점수로만 판정(단일 지표화하되, 그 산식 자체를 투명하게
    남겨 사람이 검토 가능하게 한다 - materiality_assessment 필드에 원본 6축을 그대로
    함께 저장)."""
    for dim in quality_comparison:
        assert dim in _QUALITY_DIMS, f"unknown quality dimension: {dim}"
    return sum(_QUALITY_SCORE.get(v, 0) for v in quality_comparison.values())


def classify_revision_type(relationship, materiality_score, is_boundary_condition=False):
    assert relationship in _RELATIONSHIPS, f"unknown relationship: {relationship}"
    if relationship == "SUPPORTS":
        return "NO_REVISION_NEEDED"
    if is_boundary_condition:
        return "BOUNDARY_CONDITION"
    if relationship == "EXTENDS":
        return "EXPAND_SCOPE"
    if relationship == "CONTRADICTS" and materiality_score >= _REVERSE_MATERIALITY_THRESHOLD:
        return "REVERSE"
    if materiality_score >= _QUALIFY_MATERIALITY_THRESHOLD:
        if relationship == "WEAKENS":
            return "WEAKEN"
        if relationship == "QUALIFIES":
            return "QUALIFY"
        return "PARTIAL_REVISE"  # CONTRADICTS인데 REVERSE 문턱 미달 - 강하게 뒤집지 않는다
    if materiality_score > 0:
        return "QUALIFY"
    return "NO_REVISION_NEEDED"


def _new_id(query_id, target_note_id, now_iso):
    h = hashlib.sha1(f"{query_id}|{target_note_id}|{now_iso}".encode("utf-8")).hexdigest()[:16]
    return f"vrc_{h}"


def new_view_revision_candidate(query_id, target_note_id, previous_statement, previous_claim_ceiling,
                                 new_evidence_note_ids, evidence_family_count, relationship,
                                 quality_comparison, proposed_statement, now_iso,
                                 is_boundary_condition=False, trigger_reasons=None):
    trigger_reasons = trigger_reasons or []
    for t in trigger_reasons:
        assert t in TRIGGER_REASONS, f"unknown trigger reason: {t}"

    materiality_score = compute_materiality(quality_comparison)
    revision_type = classify_revision_type(relationship, materiality_score, is_boundary_condition)
    assert revision_type in REVISION_TYPES
    novelty_kind = novelty_kind_for_relationship(relationship)

    candidate = {
        "revision_candidate_id": _new_id(query_id, target_note_id, now_iso),
        "query_id": query_id,
        "target_note_id": target_note_id,
        "previous_statement": previous_statement,
        "previous_claim_ceiling": previous_claim_ceiling,
        "new_evidence_note_ids": list(new_evidence_note_ids),
        "evidence_family_count": evidence_family_count,
        "trigger_reasons": trigger_reasons,
        "revision_type": revision_type,
        "proposed_statement": proposed_statement,
        "materiality_assessment": dict(quality_comparison),
        "materiality_score": materiality_score,
        "novelty_kind": novelty_kind,
        "status": "PENDING_HUMAN_REVIEW",
        "requires_human_approval": True,
        "human_review_status": "UNREVIEWED",
        "created_at": now_iso,
    }
    assert len(candidate) == 17, f"view revision candidate must carry exactly 17 fields, got {len(candidate)}"
    return candidate


def _load():
    if not VIEW_REVISION_PATH.exists():
        return []
    try:
        with open(VIEW_REVISION_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save(entries):
    with open(VIEW_REVISION_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=1)
        f.write("\n")


def save_candidate(candidate):
    """view_revision_candidates.json에만 쓴다 - knowledge_memory/notes.json은 절대
    건드리지 않는다(이 함수도, 이 모듈 전체도 그 파일의 경로조차 모른다)."""
    entries = _load()
    entries.append(candidate)
    _save(entries)
    return candidate


def list_candidates(status=None):
    entries = _load()
    if status is None:
        return entries
    return [e for e in entries if e["status"] == status]


def approve_candidate(revision_candidate_id):
    """사람이 명시적으로 승인했을 때만 호출된다(운영자 UI/API는 Phase L 이후 구현 -
    지금은 상태 전이 함수만 존재). 이 함수도 canonical memory를 쓰지 않는다 - 승인은
    "사람이 검토를 마쳤다"는 기록일 뿐, canonical 승격은 별도의 아직 만들어지지 않은
    단계의 몫이다."""
    entries = _load()
    matched = None
    for e in entries:
        if e["revision_candidate_id"] == revision_candidate_id:
            e["status"] = "APPROVED"
            e["human_review_status"] = "APPROVED"
            matched = e
    _save(entries)
    return matched


def previous_view_context_from_history(history_entries, note_id):
    """Operator History를 Evidence가 아니라 "이전에 이런 걸 물어봤다/이런 답을
    받았다"는 참고 맥락으로만 쓴다(섹션 16 Te 지시) - retriever.py는 여전히 이 함수도,
    history 모듈 자체도 전혀 참조하지 않는다(test_phase_j_k.py가 이미 소스 레벨로
    검증; 이 파일이 추가되어도 그 검증은 깨지지 않는다)."""
    return [h for h in history_entries if note_id in (h.get("retrieved_object_ids") or [])]
