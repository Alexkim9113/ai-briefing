# STAGE 6 — SUBSTEP F: Typed Relations(섹션 14-15, 33-34). 이 파일이 코드로 스스로
# 만드는 관계는 오직 "명시적인 구조적 소속"에서 나온 것뿐이다 — 키워드 겹침만으로 관계를
# 만들지 않는다(섹션 33). CAUSES 같은 강한 인과관계는 여기서 절대 자동 생성하지 않는다
# (섹션 15) — 그런 관계는 사람/LLM candidate 검토를 거쳐야 하며 이번 Foundation 범위 밖.
from common import stable_relation_id
from schema import new_relation_shell


def build_structural_relations(notes, now_iso):
    """EVENT/CHANGE Note가 같은 FACT/EVENT의 document_id를 공유하면 LEADS_TO가 아니라
    가장 보수적인 RELATED_TO만 만든다 — 진짜 lineage(예: CHANGE가 특정 EVENT들의 집합에서
    나왔다는 명시적 참조)가 있을 때만 SUPPORTS를 쓴다."""
    relations = []
    by_document = {}
    for note in notes:
        for did in note.get("document_ids", []):
            by_document.setdefault(did, []).append(note["note_id"])

    seen_pairs = set()
    for did, note_ids in by_document.items():
        if len(note_ids) < 2:
            continue
        note_ids = sorted(set(note_ids))
        for i in range(len(note_ids)):
            for j in range(i + 1, len(note_ids)):
                pair = (note_ids[i], note_ids[j])
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                rel = new_relation_shell(
                    stable_relation_id(pair[0], "RELATED_TO", pair[1]),
                    pair[0], "RELATED_TO", pair[1], now_iso)
                rel["evidence_ids"] = [did]
                relations.append(rel)

    return relations


def graph_quality_metrics(notes, relations):
    """섹션 34/66: 그래프 폭발 감지 — RELATED_TO 비율이 지배적이면 품질 실패로 본다."""
    total = len(relations)
    related_to = sum(1 for r in relations if r["relation_type"] == "RELATED_TO")
    note_ids_with_relation = set()
    for r in relations:
        note_ids_with_relation.add(r["subject_id"])
        note_ids_with_relation.add(r["object_id"])
    orphan_notes = [n["note_id"] for n in notes if n["note_id"] not in note_ids_with_relation]
    return {
        "notes": len(notes),
        "relations": total,
        "relations_per_note": round(total / len(notes), 3) if notes else 0,
        "related_to_ratio": round(related_to / total, 3) if total else 0,
        "orphan_notes": len(orphan_notes),
        # 섹션 66: RELATED_TO가 대부분이면 실패로 본다 — 이번 Foundation의 유일한 관계
        # 생성 규칙이 RELATED_TO이므로 이 비율은 항상 1.0에 가깝다는 것을 정직하게 표시하고,
        # 다음 단계(타입 있는 관계를 늘리는 일)가 필요하다는 신호로 남긴다.
        "graph_quality_flag": "RELATED_TO_DOMINATED" if total and related_to / total > 0.8 else "OK",
    }
