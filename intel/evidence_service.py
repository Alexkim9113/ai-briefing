# EVIDENCE + REPORTS_ON Pilot. 이번 Pilot은 "얼마나 많이 연결했는가"가 목표가 아니라
# DOCUMENT → EVIDENCE → FACT, SECONDARY → REPORTS_ON → PRIMARY 구조가 실제 데이터에서
# 안전하게(오탐 없이, 재실행해도 같은 결과로) 작동하는지 검증하는 것이다(운영자 지시).
#
# 이번 단계는 EXACT IDENTIFIER(DOI/arXiv ID)만 쓴다. 외부 API·검색·LLM·퍼지매칭은 전혀 안 쓴다.
import hashlib
import re

EVIDENCE_TYPES = ("IDENTIFIER_METADATA", "OFFICIAL_URL", "PUBLISHER_SUMMARY")
PRIMARY_STATUS = ("PRIMARY", "SECONDARY", "UNKNOWN")
SOURCE_AUTHORITY = ("OFFICIAL", "ACADEMIC", "INSTITUTIONAL", "MEDIA", "COMPANY", "OTHER")
# "SOURCE_VERIFIED"는 이번 Pilot에서 절대 만들지 않는다(운영자 지시 6번: 자동 승격 금지) —
# 목록에는 향후 호환을 위해 남겨 두되, 이 모듈은 SOURCE_LOCATED까지만 부여한다.
VERIFICATION_STATUS = ("SOURCE_VERIFIED", "SOURCE_LOCATED", "SUMMARY_DERIVED", "UNVERIFIED")
PEER_REVIEW_STATUS = ("PEER_REVIEWED", "PREPRINT", "UNKNOWN", "NOT_APPLICABLE")
VERIFICATION_SCOPE = ("METADATA", "CONTENT", "CLAIM")

_ARXIV_ID = re.compile(r"(?:arxiv[:\s]*|arxiv\.org/(?:abs|pdf)/)?(\d{4}\.\d{4,5})(v\d+)?", re.I)
_DOI = re.compile(r"(?:https?://doi\.org/|doi:\s*)?(\b10\.\d{4,9}/[^\s,\"')]+)", re.I)


def normalize_doi(raw):
    """DOI는 대개 대소문자 구분을 안 하는 관례라 매칭 키는 소문자로 통일하되, 원본 표기는 따로 보존한다."""
    doi = raw.strip().rstrip(".,)")
    doi = re.sub(r"^https?://doi\.org/", "", doi, flags=re.I)
    doi = re.sub(r"^doi:\s*", "", doi, flags=re.I)
    return {"raw": raw, "normalized": doi.lower()}


def normalize_arxiv_id(raw, version=None):
    """arXiv:2509.12345, https://arxiv.org/abs/2509.12345v2, 2509.12345 를 모두 같은 것으로 본다.
    버전(v1/v2)은 매칭 키에서는 떼어내고(같은 논문의 다른 버전은 같은 연구), base_id와 version을 따로 남긴다."""
    base = raw.strip()
    return {"raw": raw + (version or ""), "normalized": base, "version": version or None}


def extract_identifiers(text):
    """제목+요약에서 DOI/arXiv ID를 찾는다. 이번 Pilot은 이 두 종류만 본다(운영자 지시 1번)."""
    text = text or ""
    out = []
    for m in _ARXIV_ID.finditer(text):
        if m.group(1):
            out.append(("ARXIV_ID", normalize_arxiv_id(m.group(1), m.group(2))))
    for m in _DOI.finditer(text):
        out.append(("DOI", normalize_doi(m.group(1))))
    return out


def _text_hash(text):
    return hashlib.sha1((text or "").encode("utf-8", "ignore")).hexdigest()[:16]


def build_evidence_for_document(document, is_primary, identifiers):
    """DOCUMENT 하나에 대한 EVIDENCE 레코드. 원문 전체는 절대 저장하지 않고(13번),
    locator(어디서 왔는지)와 identifier·hash만 남긴다."""
    now = document.get("updated_at")
    ident = identifiers[0][1]["normalized"] if identifiers else None
    is_academic = document.get("document_type") == "RESEARCH" or (identifiers and identifiers[0][0] == "ARXIV_ID")
    return {
        "evidence_id": f"ev_{document['document_id']}",
        "document_id": document["document_id"],
        "evidence_type": "IDENTIFIER_METADATA" if identifiers else "PUBLISHER_SUMMARY",
        "locator": "rss_description" if not identifiers else "identifier_in_title_or_description",
        "identifier": ident,
        "text_hash": _text_hash(document.get("title", "")),
        "claim_scope": None,  # 이번 Pilot은 "논문이 존재한다"만 확인(METADATA), 주장 범위는 안 다룸
        "primary_status": "PRIMARY" if is_primary else ("UNKNOWN" if not identifiers else "SECONDARY"),
        "source_authority": "ACADEMIC" if is_academic else "OTHER",
        # 이번 Pilot은 "이 식별자가 실제로 존재한다"만 코드로 확인 — 논문 내용(결론·수치)은 검증하지 않았다(7,8번).
        "verification_status": "SOURCE_LOCATED" if is_primary else "SUMMARY_DERIVED",
        "verification_scope": "METADATA",
        "peer_review_status": "PREPRINT" if is_academic else "UNKNOWN",
        "created_at": now, "updated_at": now,
    }


def _rel_id(from_id, to_id, rel_type):
    """멱등성(10번): 같은 (from,to,type)이면 항상 같은 id → 재실행해도 새로 안 늘어난다."""
    return "rel_" + hashlib.sha1(f"{from_id}|{to_id}|{rel_type}".encode()).hexdigest()[:16]


def resolve_reports_on(documents_by_id, arxiv_index, doi_index):
    """EXACT IDENTIFIER ONLY. Secondary 문서에서 찾은 식별자가 '자기 자신이 아닌 다른' 문서를
    가리킬 때만 REPORTS_ON을 만든다. 자기 자신을 가리키면(예: 저널이 자기 DOI를 소개글에 적은 경우)
    이는 관계가 아니라 그 문서 자체의 근거이므로 SELF_REFERENCE로 분리해 보고한다(정확도 우선)."""
    relationships, review = {}, []
    for did, doc in documents_by_id.items():
        idents = doc.get("_identifiers") or []
        if not idents:
            continue
        for kind, norm in idents:
            index = arxiv_index if kind == "ARXIV_ID" else doi_index
            target = index.get(norm["normalized"])
            if target is None:
                review.append({"document_id": did, "identifier": norm["normalized"], "kind": kind, "result": "NO_MATCH"})
            elif target == did:
                review.append({"document_id": did, "identifier": norm["normalized"], "kind": kind, "result": "SELF_REFERENCE"})
            else:
                rid = _rel_id(did, target, "REPORTS_ON")
                relationships[rid] = {
                    "relationship_id": rid, "type": "REPORTS_ON", "from_document_id": did, "to_document_id": target,
                    "match_method": kind, "match_confidence": 0.95,  # 정확 일치지만 사람 검토 전까지 1.0은 안 씀(3번)
                    "matched_identifier": norm["normalized"], "created_at": doc.get("updated_at"),
                }
                review.append({"document_id": did, "identifier": norm["normalized"], "kind": kind,
                                "result": "MATCH", "to_document_id": target})
    return relationships, review
