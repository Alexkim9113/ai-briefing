# PRODUCTION EVIDENCE SUPPLY v1.0 — SUBSTEP E/F (섹션 12-19, Te 2026-09-29 승인).
# 실제 전체 Production corpus(intel/documents.json, 569건)에 대해 REPORTS_ON을 실제로
# 계산해서 intel/relationships.json에 쓴다. evidence_service.resolve_reports_on()의
# 의미론(EXACT IDENTIFIER ONLY, 추측 연결 금지, SELF_REFERENCE 분리)은 그대로 재사용하고
# 다시 구현하지 않는다 — 이 파일이 새로 하는 일은 "그 함수를 옛날 Phase-3A 파일럿
# (normalize.py, daily.yml에 연결 안 됨, ~500건 샘플만) 대신 실제 전체 corpus에 대해
# 실제로 실행하고 그 결과를 Evidence Pipeline이 실제로 읽는 파일(intel/relationships.json)
# 에 쓰는 것"뿐이다. normalize.py 자체는 건드리지 않는다(Phase-3A 파일럿을 Production으로
# "승격"시키지 말라는 지시를 그대로 지킨다 — 새 adapter를 쓴다).
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
INTEL_DIR = ROOT / "intel"
sys.path.insert(0, str(INTEL_DIR))
from evidence_service import extract_identifiers, resolve_reports_on  # noqa: E402

_PRIMARY_ARXIV_URL = re.compile(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})", re.I)
_PRIMARY_DOI_URL = re.compile(r"doi\.org/(10\.\d{4,9}/[^\s,\"')]+)", re.I)
_NATURE_DOI = re.compile(r"nature\.com/articles/([a-z0-9.\-]+)", re.I)

# SUBSTEP E(섹션 12): exact identifier 확장 후보 — 실제 corpus에 원문 case_number/
# bill_number/regulation_number 필드가 아직 없으므로(Court/Law Primary 문서 자체가 0건,
# Spec2에서 이미 확인) 이 시점에는 "인식만 하고 매칭은 안 되는" 정직한 빈 상태로 둔다.
# 실제 court/law Primary 문서가 Collection에 들어오기 전까지는 여기서 매칭이 생길 수 없다
# (섹션 58: PENDING을 억지로 채우지 않는다).
_CASE_NUMBER_RE = re.compile(r"\b\d{4}[A-Z]{1,4}\d{2,8}\b")  # 예시 형태만, 현재 corpus엔 없음(플레이스홀더 인식용)


def load_documents():
    return json.loads((INTEL_DIR / "documents.json").read_text(encoding="utf-8"))


def load_raw_items_by_id():
    by_id = {}
    for f in ROOT.glob("data/2026-*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for it in d.get("items", []):
            by_id[it["id"]] = it
    return by_id


def _own_identifier_of(doc):
    """이 문서 '자신'이 그 논문/원자료 자체인지(자기 정체성) — 텍스트 내 언급이 아니라
    canonical_url이 실제 저장소/DOI 도메인일 때만 판정한다(추측 금지)."""
    url = doc.get("canonical_url") or ""
    m = _PRIMARY_ARXIV_URL.search(url)
    if m:
        return "ARXIV_ID", m.group(1)
    m = _PRIMARY_DOI_URL.search(url)
    if m:
        return "DOI", m.group(1).lower()
    m = _NATURE_DOI.search(url)
    if m:
        return "DOI", f"10.1038/{m.group(1)}".lower()
    return None, None


def run(write_output=True):
    documents = load_documents()
    docs_list = documents if isinstance(documents, list) else list(documents.values())
    documents_by_id = {d["document_id"]: d for d in docs_list}
    raw_items = load_raw_items_by_id()

    arxiv_index, doi_index = {}, {}
    for did, doc in documents_by_id.items():
        kind, norm_id = _own_identifier_of(doc)
        if kind == "ARXIV_ID":
            arxiv_index[norm_id] = did
        elif kind == "DOI":
            doi_index[norm_id] = did

    case_number_hits = 0
    for did, doc in documents_by_id.items():
        raw = raw_items.get(did) or {}
        text = f"{doc.get('title', '')}\n{raw.get('summary') or ''}"
        idents = extract_identifiers(text)
        doc["_identifiers"] = idents  # 이번 실행 메모리 상에서만(문서.json 파일 자체는 건드리지 않음)
        if _CASE_NUMBER_RE.search(text):
            case_number_hits += 1

    relationships, review = resolve_reports_on(documents_by_id, arxiv_index, doi_index)

    metrics = {
        "documents_examined": len(documents_by_id),
        "arxiv_primary_documents": len(arxiv_index),
        "doi_primary_documents": len(doi_index),
        "case_number_pattern_hits_unmatched": case_number_hits,
        "reports_on_relationships_created": len(relationships),
        "identifier_candidates_reviewed": len(review),
        "self_references": sum(1 for r in review if r["result"] == "SELF_REFERENCE"),
        "no_match": sum(1 for r in review if r["result"] == "NO_MATCH"),
        "matches": sum(1 for r in review if r["result"] == "MATCH"),
        "note": ("case_number 패턴은 인식되지만 corpus에 Court/Law Primary 문서 자체가 없어 "
                 "실제 매칭은 0건이다 — 이는 결함이 아니라 Collection 단계의 한계(SUBSTEP D가 "
                 "먼저 해결해야 할 부분)이며, 억지로 채우지 않았다."),
    }

    if write_output:
        (INTEL_DIR / "relationships.json").write_text(
            json.dumps(relationships, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        out_path = Path(__file__).resolve().parent / "reports_on_runner_metrics.json"
        out_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        review_path = Path(__file__).resolve().parent / "reports_on_runner_review.json"
        review_path.write_text(json.dumps(review, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    return metrics, relationships, review


if __name__ == "__main__":
    m, *_ = run()
    print(json.dumps(m, ensure_ascii=False, indent=1))
