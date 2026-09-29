# 5D ADAPTER(운영자 지시 섹션 29 — "이번 작업의 핵심"). structural_analysis_layer 코드는
# 절대 수정하지 않는다 — 그 Layer가 이미 읽도록 만들어 둔 정확한 입력 파일 형식
# (intel/structural_analysis_layer/structural_evidence_input.json, run()의
# load_evidence_records()가 읽는 경로)에 맞춰 이 Evidence Pipeline의 Interpretation
# Candidate를 변환해 쓰기만 한다. 원문 기사/요약/mx.b/mx.p는 절대 이 파일에 담지 않는다 —
# 오직 이미 구조화된 Evidence Record만 전달한다(운영자 지시: raw document를 5D에 직접
# 먹이지 않음).
from schema import FIVE_D_TARGET_TYPES


def _active_structural_changes(structural_changes):
    return {scid: sc for scid, sc in (structural_changes or {}).items()
            if sc.get("status") != "REJECTED" and sc.get("override_status") != "HUMAN_REJECTED"}


def _matches(sc, rec):
    """entity 또는 domain 겹침이 있어야만 연결한다 — 임의의 Structural Change에 아무
    Evidence나 갖다 붙이지 않는다(섹션 29: 근거 없는 연결 금지)."""
    sc_entities, rec_entities = set(sc.get("entities", [])), set(rec.get("entities", []))
    sc_domains, rec_domains = set(sc.get("domains", [])), set(rec.get("domains", []))
    return bool(sc_entities & rec_entities) or bool(sc_domains & rec_domains)


def _rejected(rec):
    return rec.get("human_review_status") == "HUMAN_REJECTED" or rec.get("support_type") == "CONTRADICTORY"


def build_structural_evidence_input(evidence_records, structural_changes):
    """evidence_records: evidence_record_id -> dict(evidence_pipeline 산출물).
    structural_changes: structural_change_id -> dict(structural_change_layer, 읽기 전용).
    반환: 5D pipeline.run()의 evidence_records_override와 정확히 같은 shape(list of dict)."""
    active_sc = _active_structural_changes(structural_changes)
    out = []
    skipped_no_match, skipped_rejected = 0, 0
    for rec in (evidence_records or {}).values():
        if rec.get("evidence_type") not in FIVE_D_TARGET_TYPES:
            continue
        if _rejected(rec):
            skipped_rejected += 1
            continue
        ts = rec.get("_type_specific") or {}
        matched_any = False
        for scid, sc in active_sc.items():
            if not _matches(sc, rec):
                continue
            matched_any = True
            item = {
                "type": rec["evidence_type"], "structural_change_id": scid,
                "supporting_pattern_ids": [], "supporting_change_ids": [], "supporting_event_ids": [],
                "counter_evidence_ids": list(rec.get("contradicts_ids", [])),
                "domains": list(rec.get("domains", [])), "entities": list(rec.get("entities", [])),
                "institutions": [], "resources": list(rec.get("resources", [])),
                "first_seen": rec.get("first_seen"), "last_seen": rec.get("last_seen"),
                "_source_evidence_record_id": rec["evidence_record_id"],
            }
            item.update(ts)
            out.append(item)
        if not matched_any:
            skipped_no_match += 1
    return out, {"skipped_no_active_structural_change_match": skipped_no_match,
                 "skipped_rejected_or_contradictory": skipped_rejected,
                 "active_structural_changes": len(active_sc)}
