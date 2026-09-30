# CONDITIONAL-PASS CLOSURE item 2 — RSS→Article→Reference provenance pipeline
# (forward-looking only, NOT a backfill). Te가 지적한 "missing link"를 메운다:
# 오늘 RSS 경로는 title+description만 저장하고 원문 본문/하이퍼링크를 저장하지 않아서
# REPORTS_ON과 link_provenance가 실제 corpus에서 항상 0건이 된다(구조적 데이터 모델
# 한계, reports_on_expansion.py 상단 docstring 참고). 이 모듈은 그것을 소급 백필하지
# 않는다 - 대신 "만약 앞으로 어떤 article URL이 content_acquisition.acquire_content()를
# 통해 FULL_TEXT/PARTIAL_TEXT를 확보하게 된다면" 그 HTML을 받아
# 본문 -> 외부 링크 -> 1차 출처 후보 -> REPORTS_ON 레코드까지 이어지는 결정론적 체인
# 전체가 실제로 동작함을 보장한다(synthetic fixture로 end-to-end 검증).
#
# REUSE BEFORE BUILD: 링크 추출/allowlist 판정은 link_provenance.py를 그대로 쓴다.
# REPORTS_ON 레코드 생성은 reports_on_expansion.build_relationship_record()를 그대로
# 쓴다. 이 모듈은 두 기존 모듈을 연결하는 접착제일 뿐, 새 매칭 로직을 만들지 않는다.
#
# LLM/퍼지 매칭 없음 - link_provenance가 이미 결정론적 도메인 allowlist만 쓰고,
# reports_on_expansion도 EXACT URL/제목 매치만 쓴다(그 성질을 그대로 상속한다).
#
# MINIMAL STORAGE (섹션 11): 이 모듈은 전체 본문(text)을 자신의 반환값이나 새 파일에
# 영구 저장하지 않는다. 호출자에게 반환하는 레코드에는 content_hash(sha256)와 최소
# 메타데이터, 그리고 (이미 짧게 truncate된) link_provenance 후보 리스트만 담는다 -
# 원문 body 자체를 새 저장 경로로 만들지 않는다(content_acquisition.py도 애초에
# acquire_content()의 반환값을 영구 파일에 쓰지 않으며, 이 모듈도 그 관례를 그대로
# 따른다 - 호출자가 알아서 즉시 폐기해야 하는 것은 text 필드뿐이다).
import hashlib
from datetime import datetime, timezone

import link_provenance
import sys
from pathlib import Path

# reports_on_expansion.py는 intel/operator_brain/에 있고, 이 파일과 이름이 겹치는
# 모듈(schema.py)이 intel/source_intelligence/에도 있으므로, 정해진
# importlib.util.spec_from_file_location() 격리 패턴을 그대로 쓴다 - bare sys.path
# insert로 두 schema.py가 충돌하지 않게 한다.
import importlib.util

_HERE = Path(__file__).resolve().parent
_OPERATOR_BRAIN_DIR = _HERE.parent / "operator_brain"


def _load_reports_on_expansion():
    spec = importlib.util.spec_from_file_location(
        "reports_on_expansion", _OPERATOR_BRAIN_DIR / "reports_on_expansion.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_reports_on_expansion = _load_reports_on_expansion()


def _sha256(text):
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def process_acquired_article(source_document_id, acquired, html, source_url,
                              known_documents_by_id=None):
    """체인 전체: acquired(content_acquisition.acquire_content()의 반환값) + html(그
    호출에 쓰였던 원본 HTML, 호출자가 들고 있는 것을 그대로 넘겨받는다 - 이 함수는
    fetch를 직접 하지 않는다) -> 외부 링크 -> 1차 출처 후보 -> (가능하면) REPORTS_ON.

    known_documents_by_id: {document_id: {"canonical_url":..., "title":...}} - 이미
    corpus에 있는 문서들. 링크가 가리키는 URL이 이 corpus의 어떤 document의
    canonical_url과 EXACT하게 같을 때만 REPORTS_ON을 만든다(추측/발명 금지 - "reference가
    없으면 관계를 발명하지 않는다"). None이면 REPORTS_ON 생성 단계는 건너뛴다(빈 리스트).

    반환: {
      "source_document_id", "content_hash", "content_status",
      "link_candidates": [...],  # link_provenance 레코드(이미 앵커 텍스트 40자 truncate됨)
      "reports_on_records": [...],  # 0개 이상, 발명 없이 exact match만
    }
    본문(text) 자체는 이 반환 dict에 담지 않는다(MINIMAL STORAGE)."""
    content_status = (acquired or {}).get("status")
    text = (acquired or {}).get("text")
    content_hash = _sha256(text) if text else None

    link_candidates = link_provenance.extract_link_provenance_candidates(
        source_document_id, html, content_status)

    reports_on_records = []
    if known_documents_by_id:
        # source_url 정규화된 canonical_url -> document_id 역인덱스를 만든다(exact match만).
        by_canonical = {}
        for did, doc in known_documents_by_id.items():
            canon = doc.get("canonical_url")
            if canon:
                by_canonical[_reports_on_expansion._norm_url(canon)] = did

        for cand in link_candidates:
            target_id = by_canonical.get(_reports_on_expansion._norm_url(cand["link_url"]))
            if not target_id or target_id == source_document_id:
                continue  # 정확히 일치하는 corpus 내 문서가 없으면 관계를 발명하지 않는다
            rec = _reports_on_expansion.build_relationship_record(
                source_document_id=source_document_id,
                target_document_id=target_id,
                resolution_method="EXACT_URL_MATCH",
                resolution_confidence=0.95,
                explicit_identifier=cand["link_url"],
                source_url=source_url,
                target_url=cand["link_url"],
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            reports_on_records.append(rec)

    return {
        "source_document_id": source_document_id,
        "content_hash": content_hash,
        "content_status": content_status,
        "link_candidates": link_candidates,
        "reports_on_records": reports_on_records,
    }
