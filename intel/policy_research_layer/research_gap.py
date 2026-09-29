# PHASE 5G — Research Gap(운영자 지시 30~32번). Research Gap != Evidence of Absence —
# "아무도 연구하지 않았다"가 아니라 현재 축적된 근거가 특정 질문을 해결하기에 부족하다는 뜻.
from common import hash_id
from schema import new_research_gap_shell, RESEARCH_GAP_TYPES, PRIORITY_LEVELS


def generate_research_gap_candidates(evidence_records, target_index):
    out = {}
    for rec in evidence_records or []:
        if rec.get("type") != "RESEARCH_GAP":
            continue
        gap_type = rec.get("gap_type")
        if gap_type not in RESEARCH_GAP_TYPES:
            continue
        description_code = rec.get("gap_description_code")
        if not description_code:
            continue
        target_type, target_id = rec.get("target_object_type"), rec.get("target_object_id")
        priority = rec.get("priority")
        if priority not in PRIORITY_LEVELS:
            priority = "LOW"
        gid = hash_id("rgap", f"{target_type}|{target_id}|{gap_type}|{description_code}")
        shell = new_research_gap_shell(gid, target_type, target_id, gap_type, description_code,
                                        rec.get("scope"), priority)
        shell["known_evidence_ids"] = list(rec.get("known_evidence_ids", []))
        shell["missing_evidence_types"] = list(rec.get("missing_evidence_types", []))
        shell["affected_questions"] = list(rec.get("affected_questions", []))
        out[gid] = shell
    return out
