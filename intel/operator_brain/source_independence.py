# STAGE 7 PHASE G-K CHECKPOINT REMEDIATION (item 1/3) — Source Independence.
# Te 지시: 새 source-truth 시스템을 만들지 않는다. 기존 Stage 1-6 provenance 신호만
# 재사용한다 - document_id 동일성(knowledge_memory notes.json), canonical_url
# (documents.json), evidence_supply의 REPORTS_ON 관계(intel/relationships.json,
# evidence_supply/reports_on_runner.py가 실제로 계산해서 쓰는 파일 - 그 계산을 다시
# 구현하지 않고 결과만 읽는다). 상태는 정성적 어휘(질적 판단)만 쓴다 - 숫자 "독립성
# 점수" 같은 단일 합성 지표는 만들지 않는다(evidence_sufficiency.py의 "단일 Truth
# Score 금지" 원칙과 동일 정신).
import json
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
INTEL_DIR = HERE.parent

INDEPENDENCE_STATUSES = (
    "INDEPENDENT", "LIKELY_INDEPENDENT", "SHARED_ORIGIN",
    "DERIVED_FROM_SAME_SOURCE", "UNKNOWN",
)

# 우선순위(여러 pair 중 전체 대표값을 고를 때): 확정적으로 묶인 관계가 가장 먼저 이기고,
# 그 다음은 "모른다"(UNKNOWN)가 "독립적이라고 확신한다"보다 더 보수적으로 앞선다 - 모르면
# 독립적이라고 우기지 않는다(섹션 4 Te 지시).
_PRIORITY = ["SHARED_ORIGIN", "DERIVED_FROM_SAME_SOURCE", "UNKNOWN",
             "LIKELY_INDEPENDENT", "INDEPENDENT"]


def _domain(url):
    if not url:
        return None
    try:
        netloc = urlparse(url).netloc.lower()
        return netloc[4:] if netloc.startswith("www.") else netloc
    except Exception:
        return None


def _load_relationships_file(path):
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()
    rows = data if isinstance(data, list) else list(data.values())
    pairs = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        a = row.get("from_document_id") or row.get("source_document_id") or row.get("document_id")
        b = row.get("to_document_id") or row.get("target_document_id") or row.get("reports_on_document_id")
        if a and b:
            pairs.add(frozenset((a, b)))
    return pairs


def load_reports_on_pairs():
    """intel/relationships.json — evidence_supply.reports_on_runner.run()이 실제
    corpus에 대해 계산해 쓰는 REPORTS_ON(DOI/arXiv) 결과 파일. 이 모듈은 그 계산 로직
    (evidence_service.resolve_reports_on)을 다시 만들지 않고 그 출력만 읽는다. 파일이
    없거나 비어 있으면(현재 corpus: 0건) 정직하게 빈 집합을 반환한다 - 추측 연결 금지.

    SOURCE INTELLIGENCE remediation (item 5): DOI/arXiv 외에 REPORTS_ON을 확장한
    intel/relationships_company_gov.json(reports_on_expansion.py)이 있으면 합쳐서
    반환한다 - source_independence.py 자체의 어휘(INDEPENDENT/... 등)는 그대로 두고,
    이 함수가 읽는 "REPORTS_ON pair 후보 집합"만 넓힌다."""
    pairs = _load_relationships_file(INTEL_DIR / "relationships.json")
    pairs |= _load_relationships_file(INTEL_DIR / "relationships_company_gov.json")
    return pairs


def pairwise_status(prov_a, prov_b, reports_on_pairs=None):
    """provenance.reconstruct()가 만드는 trail entry 두 개(document_id/canonical_url/found)
    를 비교한다. 판단할 실제 신호가 없으면 UNKNOWN으로 남긴다 - 모르면 독립적이라고도,
    같은 출처라고도 우기지 않는다."""
    reports_on_pairs = reports_on_pairs or set()
    if not prov_a.get("found") or not prov_b.get("found"):
        return "UNKNOWN"

    doc_a, doc_b = prov_a.get("document_id"), prov_b.get("document_id")
    if doc_a and doc_b and doc_a == doc_b:
        return "SHARED_ORIGIN"

    if doc_a and doc_b and frozenset((doc_a, doc_b)) in reports_on_pairs:
        return "DERIVED_FROM_SAME_SOURCE"

    url_a, url_b = prov_a.get("canonical_url"), prov_b.get("canonical_url")
    if url_a and url_b and url_a == url_b:
        return "SHARED_ORIGIN"

    domain_a, domain_b = _domain(url_a), _domain(url_b)
    if domain_a and domain_b:
        return "DERIVED_FROM_SAME_SOURCE" if domain_a == domain_b else "INDEPENDENT"

    # url이 하나라도 없으면(예: Google News redirect가 아직 해석되지 않음) 도메인
    # 비교가 불가능하다 - 문서 자체는 서로 다르므로 완전한 UNKNOWN보다는 정보가 있지만,
    # INDEPENDENT라고 확정할 근거는 없다.
    if doc_a and doc_b and doc_a != doc_b:
        return "LIKELY_INDEPENDENT"
    return "UNKNOWN"


def _best_status(statuses):
    for p in _PRIORITY:
        if p in statuses:
            return p
    return "UNKNOWN"


def assess_independence(provenance_trails, reports_on_pairs=None):
    """provenance_trails: [(note_id, [trail_entry, ...]), ...] (provenance.reconstruct()
    출력 그대로). note 쌍마다 가장 확정적인 status를 매기고, SHARED_ORIGIN/
    DERIVED_FROM_SAME_SOURCE로 묶이는 note들을 evidence_family로 그룹화한다(union-find).
    family 계산 자체가 새 source-truth가 아니라 - 이미 있는 pairwise 신호를 그룹으로
    엮어 보여주는 것뿐이다. reports_on_pairs를 명시적으로 주면(테스트용) 그것을 쓰고,
    없으면 실제 intel/relationships.json을 읽는다."""
    reports_on_pairs = load_reports_on_pairs() if reports_on_pairs is None else reports_on_pairs
    note_ids = [nid for nid, _ in provenance_trails]
    trails_by_id = dict(provenance_trails)
    parent = {nid: nid for nid in note_ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    pair_statuses = {}
    for i in range(len(note_ids)):
        for j in range(i + 1, len(note_ids)):
            n_a, n_b = note_ids[i], note_ids[j]
            statuses_seen = [
                pairwise_status(ea, eb, reports_on_pairs)
                for ea in trails_by_id[n_a] for eb in trails_by_id[n_b]
            ] or ["UNKNOWN"]
            best = _best_status(statuses_seen)
            pair_statuses[(n_a, n_b)] = best
            if best in ("SHARED_ORIGIN", "DERIVED_FROM_SAME_SOURCE"):
                union(n_a, n_b)

    families = {}
    for nid in note_ids:
        families.setdefault(find(nid), []).append(nid)

    if len(note_ids) <= 1:
        overall = "UNKNOWN"
    else:
        # 전체 대표 status는 "가장 확정적으로 묶인 관계"를 우선하되, 확정적 연결이
        # 없으면 "모른다"가 "독립적이다"보다 앞선다 - family 개수가 아니라 실제
        # pairwise 판정들 중 최우선 순위(_PRIORITY)를 그대로 대표값으로 쓴다.
        overall = _best_status(pair_statuses.values())

    return {
        "overall_status": overall,
        "pair_statuses": {f"{a}|{b}": v for (a, b), v in pair_statuses.items()},
        "evidence_family_count": len(families),
        "families": list(families.values()),
    }
