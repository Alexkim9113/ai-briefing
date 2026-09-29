# SOURCE INDEPENDENCE(운영자 지시 섹션 35 — "매우 중요"). 같은 통신사 기사를 20곳이 재배포해도
# 20개의 독립 소스가 아니다. 기존 intel/relationships.json(REPORTS_ON, evidence_service.py가
# EXACT IDENTIFIER로만 생성)과 intel/source_aliases.json(같은 매체의 표기 변형)을 읽기 전용으로
# 재사용한다 — 새 유사도/퍼지매칭을 만들지 않는다.


def load_source_aliases(source_aliases):
    """alias(문자열) -> canonical_name. source_id 자체가 alias 목록에 없으면 canonical_name은
    source_id 자신(=독립 소스로 취급, 과소평가 대신 보수적으로 '모르면 독립적'으로 둔다)."""
    by_source_id = {}
    for row in source_aliases or []:
        by_source_id[row["source_id"]] = row.get("canonical_name") or row["source_id"]
    return by_source_id


def _root_document(document_id, reports_on_targets):
    """REPORTS_ON 체인을 한 단계만 따라간다(evidence_service.py가 EXACT IDENTIFIER만 쓰므로
    체인이 깊지 않다 — 무한 루프 방지를 위해 1홉으로 제한, 있으면 원본, 없으면 자기 자신)."""
    return reports_on_targets.get(document_id, document_id)


def build_reports_on_index(relationships):
    """relationships.json(dict of relationship_id -> {type, from_document_id, to_document_id, ...})
    에서 REPORTS_ON만 뽑아 from->to 매핑을 만든다."""
    out = {}
    for rel in (relationships or {}).values():
        if rel.get("type") == "REPORTS_ON":
            out[rel["from_document_id"]] = rel["to_document_id"]
    return out


def compute_independence(document_ids, documents_by_id, relationships, source_aliases):
    """반환: independent_document_count(REPORTS_ON 체인 축약 후 고유 문서 수),
    independent_source_count(별칭 정규화 후 고유 매체 수). 정보가 전혀 없으면(=매핑 없음)
    보수적으로 raw count를 쓴다 — 모르는 경우 0으로 추정하지 않는다(20개 금지 12,20번)."""
    reports_on = build_reports_on_index(relationships)
    alias_map = load_source_aliases(source_aliases)

    root_docs = {_root_document(did, reports_on) for did in document_ids}
    independent_document_count = len(root_docs)

    canonical_sources = set()
    for did in root_docs:
        doc = documents_by_id.get(did)
        if not doc:
            continue
        sid = doc.get("source_id")
        canonical_sources.add(alias_map.get(sid, sid))
    independent_source_count = len(canonical_sources)

    return {
        "raw_document_count": len(set(document_ids)),
        "independent_document_count": independent_document_count,
        "independent_source_count": independent_source_count,
        "syndication_collapsed": len(set(document_ids)) - independent_document_count,
    }
