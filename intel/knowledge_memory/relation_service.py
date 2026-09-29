# STAGE 6 — PRODUCTIONIZATION v1.0 섹션 6-12: Relation Productionization. 이 파일의
# 원칙은 "NEW INFERENCE가 아니라 EXISTING RELATION PRESERVATION"(섹션 7)이다 — 여기서
# 만드는 모든 관계는 upstream에 이미 명시적으로 존재하는 소속/링크에서만 나온다. Concept
# 공유나 키워드 겹침만으로는 절대 관계를 만들지 않는다(섹션 42).
from common import stable_relation_id
from schema import new_relation_shell


def build_lineage_relations(fact_notes, event_notes, now_iso):
    """섹션 8: LINEAGE 관계 — FACT가 나온 document_id가 EVENT의 관련 문서 집합에 실제로
    속해 있을 때만 PART_OF_EVENT를 만든다. 이건 추론이 아니라 event_production이 이미
    만들어 둔 '이 문서들이 이 Event에 속한다'는 사실을 그대로 옮기는 것뿐이다."""
    relations = []
    event_doc_index = []  # [(event_note_id, event_source_id, set(doc_ids))]
    for e in event_notes:
        doc_ids = set(e.get("document_ids") or [])
        if doc_ids:
            event_doc_index.append((e["note_id"], (e.get("source_object_ids") or [None])[0], doc_ids))

    for f in fact_notes:
        f_docs = set(f.get("document_ids") or [])
        if not f_docs:
            continue
        for event_note_id, event_source_id, doc_ids in event_doc_index:
            if f_docs & doc_ids:
                rel = new_relation_shell(
                    stable_relation_id(f["note_id"], "PART_OF_EVENT", event_note_id),
                    f["note_id"], "PART_OF_EVENT", event_note_id, now_iso,
                    relation_class="LINEAGE", source_stage="event_production",
                    source_relation_id=event_source_id)
                rel["evidence_ids"] = sorted(f_docs & doc_ids)
                relations.append(rel)
    return relations


def build_semantic_relations_from_upstream(change_notes, event_notes_by_source_id, now_iso):
    """섹션 8-9: SEMANTIC 관계도 upstream이 이미 명시적으로 갖고 있을 때만 가져온다 —
    change_layer/changes.json의 supporting_event_ids/contradicting_event_ids가 그 예다.
    Stage 6은 이 관계를 '만드는' 게 아니라 '옮기는' 것이다. HUMAN_REJECTED된 change는
    호출자가 이미 걸러서 change_notes에 안 넘긴다고 가정하되, 방어적으로 다시 확인한다."""
    relations = []
    for c in change_notes:
        if c.get("status") == "REJECTED":
            continue
        change_source = (c.get("source_object_ids") or [None])[0]
        upstream = c.get("_upstream_change") or {}
        for eid in upstream.get("supporting_event_ids", []):
            target = event_notes_by_source_id.get(eid)
            if not target:
                continue
            rel = new_relation_shell(
                stable_relation_id(c["note_id"], "SUPPORTS", target),
                target, "SUPPORTS", c["note_id"], now_iso,  # EVENT supports CHANGE
                relation_class="SEMANTIC", source_stage="change_layer", source_relation_id=change_source)
            relations.append(rel)
        for eid in upstream.get("contradicting_event_ids", []):
            target = event_notes_by_source_id.get(eid)
            if not target:
                continue
            rel = new_relation_shell(
                stable_relation_id(c["note_id"], "CONTRADICTS", target),
                target, "CONTRADICTS", c["note_id"], now_iso,
                relation_class="SEMANTIC", source_stage="change_layer", source_relation_id=change_source)
            relations.append(rel)
    return relations


def dedup_relations(relations):
    """섹션 11: 같은 (subject, relation_type, object)가 여러 upstream path에서 나오면
    evidence_ids/source_relation_id를 병합하고 하나만 남긴다 — Edge를 무한 생성하지 않는다."""
    merged = {}
    for rel in relations:
        key = (rel["subject_id"], rel["relation_type"], rel["object_id"])
        if key not in merged:
            merged[key] = dict(rel)
        else:
            existing = merged[key]
            existing["evidence_ids"] = sorted(set(existing.get("evidence_ids", [])) | set(rel.get("evidence_ids", [])))
    return list(merged.values())


def graph_quality_metrics(notes, relations):
    """섹션 12/66: 그래프 폭발 감지 + lineage/semantic/revision 분해."""
    total = len(relations)
    related_to = sum(1 for r in relations if r["relation_type"] == "RELATED_TO")
    by_class = {}
    for r in relations:
        by_class[r.get("relation_class", "SEMANTIC")] = by_class.get(r.get("relation_class", "SEMANTIC"), 0) + 1

    note_ids_with_relation = set()
    for r in relations:
        note_ids_with_relation.add(r["subject_id"])
        note_ids_with_relation.add(r["object_id"])
    orphan_notes = [n["note_id"] for n in notes if n["note_id"] not in note_ids_with_relation]

    per_note_counts = {}
    for r in relations:
        per_note_counts[r["subject_id"]] = per_note_counts.get(r["subject_id"], 0) + 1
        per_note_counts[r["object_id"]] = per_note_counts.get(r["object_id"], 0) + 1
    counts_sorted = sorted(per_note_counts.values())
    median = counts_sorted[len(counts_sorted) // 2] if counts_sorted else 0

    return {
        "total_notes": len(notes),
        "total_relations": total,
        "relations_per_note": round(total / len(notes), 3) if notes else 0,
        "median_relations_per_note": median,
        "max_relations_per_note": max(counts_sorted) if counts_sorted else 0,
        "related_to_count": related_to,
        "related_to_ratio": round(related_to / total, 3) if total else 0,
        "lineage_relation_count": by_class.get("LINEAGE", 0),
        "semantic_relation_count": by_class.get("SEMANTIC", 0),
        "evidence_relation_count": by_class.get("EVIDENCE", 0),
        "revision_relation_count": by_class.get("REVISION", 0),
        "orphan_note_count": len(orphan_notes),
        "keyword_only_relation_count": 0,  # 섹션 42: 이 서비스는 keyword-only 관계를 만드는 경로 자체가 없다
        "graph_quality_flag": "RELATED_TO_DOMINATED" if total and related_to / total > 0.8 else "OK",
    }
