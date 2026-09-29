# PRODUCTION VALIDATION WATCH(운영자 지시 섹션 5). 새 Intelligence Layer가 아니라
# Readiness/Validation mechanism이다. 비용을 늘리는 별도 polling system을 만들지 않고
# (섹션 5: "비용을 증가시키는 별도 polling system을 만들지 않는다"), 이미 존재하는
# evidence_pipeline / structural_analysis_layer 실행 결과 JSON만 읽어 현재
# VERIFIED/PENDING 상태를 보고한다. 이 모듈은:
#   - 어떤 기존 파일도 쓰지 않는다(읽기 전용).
#   - 자기 자신의 출력 파일(production_validation_watch.json) 하나만 쓴다.
#   - 크론/스케줄을 새로 만들지 않는다 — 기존 evidence_pipeline 실행 뒤 수동/CI에서
#     한 번 호출하는 것을 상정한다.
#
# CONDITIONAL PASS의 5가지 사유(운영자 지시 섹션 4)를 그대로 watch 대상으로 삼는다:
#   1. Policy/Law/Court Primary 사례
#   2. Gemini Level 3 Production 실행
#   3. Counter Evidence
#   4. Dependency Evidence
#   5. Control Evidence
import json
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
INTEL_DIR = HERE.parent
REPO_ROOT = INTEL_DIR.parent
EVIDENCE_PIPELINE_DIR = INTEL_DIR / "evidence_pipeline"
STRUCTURAL_ANALYSIS_DIR = INTEL_DIR / "structural_analysis_layer"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

# PRODUCTION EVIDENCE VALIDATION v1.0(섹션 3) — Watch는 VERIFIED/PENDING 두 값만으로는
# 부족하다: "재실행했더니 깨졌다"(FAILED)와 "이 항목은 현재 아키텍처에서 평가 대상 자체가
# 아니다"(NOT_APPLICABLE)를 구분할 수 있어야 한다. 기존 두 값의 의미는 전혀 바꾸지 않고
# (VERIFIED/PENDING 판정 로직은 그대로), 어휘만 확장한다 — 이번 실행에서 FAILED/
# NOT_APPLICABLE을 실제로 만들어내는 곳은 없다(억지로 채우지 않는다, 섹션 2).
STATUS_VALUES = ("VERIFIED", "PENDING", "FAILED", "NOT_APPLICABLE")

# 정부/법원/입법/규제 공식 도메인 힌트 — evidence_pipeline/source_resolver.py와 완전히
# 동일한 상수를 다시 정의하지 않고 그 파일을 import해서 재사용하는 것이 원칙이지만, 그
# 모듈은 evidence_service/document_service/normalize를 bare import하는 구조라(sys.path
# 의존) 이 Watch가 그것까지 끌어오면 "읽기 전용 Watch"의 단순함이 깨진다. 대신 여기서는
# source_resolver.py의 실제 상수 값을 그대로 옮겨 "왜 PENDING인지"를 진단하는 목적으로만
# 쓴다(판정 자체는 여전히 claim_status/claim_type만으로 하고, 이 도메인 집합은 진단 전용).
_OFFICIAL_DOMAIN_HINTS = (
    ".go.kr", "korea.kr", "whitehouse.gov", ".gov", "europa.eu",  # document_service._GOV_DOMAIN_HINTS 발췌
    "scourt.go.kr", "supremecourt.gov", "courtlistener.com",       # source_resolver._COURT_HINTS
    "assembly.go.kr", "congress.gov", "parliament.uk",             # source_resolver._LEGISLATIVE_HINTS
    "ftc.gov", "sec.gov", "fcc.gov", "kcc.go.kr", "ftc.go.kr", "edps.europa.eu",  # _REGULATORY_HINTS
)

# claim_status 중 "실제로 원문 자리를 코드로 확인했다"고 볼 수 있는 것만 PRIMARY로 센다.
# SECONDARY_ONLY/SUMMARY_DERIVED/INSUFFICIENT_SOURCE는 아무리 개수가 많아도 Primary가 아니다
# (evidence_pipeline/claim_extractor.py의 hierarchy 판정과 동일한 원칙 재확인일 뿐,
# 그 판정 로직 자체를 다시 구현하지 않고 이미 나온 claim_status 값만 읽는다).
_PRIMARY_CLAIM_STATUSES = {"SOURCE_VERIFIED", "SOURCE_LOCATED"}
_POLICY_LAW_COURT_CLAIM_TYPES = {"GOVERNMENT_REPORTED", "LEGISLATIVE_TEXT", "REGULATORY_TEXT", "COURT_FINDING"}


def _load_json(path, default):
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def _as_list(value):
    if isinstance(value, dict):
        return list(value.values())
    return value or []


def _active_entries(entries):
    """override_status/status가 HUMAN_REJECTED인 것은 watch 대상에서 제외 — 사람이 이미
    반려한 것을 "검증됨"으로 잘못 보고하지 않는다(evidence_pipeline_overrides.json의
    human_rejected 원칙과 동일)."""
    out = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        if e.get("override_status") == "HUMAN_REJECTED" or e.get("human_review_status") == "HUMAN_REJECTED":
            continue
        out.append(e)
    return out


def _domain_of(url):
    if not url:
        return None
    try:
        return urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        return None


def _policy_law_court_diagnosis(documents):
    """왜 PENDING인지 읽기 전용으로 진단(판정 자체에는 쓰지 않음). 실제 canonical_url
    도메인 중 공식 도메인이 몇 개인지, news.google.com 리다이렉트(=도메인 판정 자체가
    원천적으로 불가능한 문서)가 몇 건인지만 센다."""
    total = official = google_news_redirect = 0
    for d in documents:
        if not isinstance(d, dict):
            continue
        total += 1
        dom = _domain_of(d.get("canonical_url"))
        if not dom:
            continue
        if dom == "news.google.com":
            google_news_redirect += 1
        elif any(h in dom for h in _OFFICIAL_DOMAIN_HINTS):
            official += 1
    return {
        "documents_examined": total,
        "official_domain_documents": official,
        "google_news_redirect_documents": google_news_redirect,
        "note": ("공식 도메인 문서가 0건이면 Collection 단계(sources.json)가 정부/법원/입법 "
                 "피드를 아직 포함하지 않는다는 뜻이며, news.google.com 리다이렉트 문서는 "
                 "실제 목적지 도메인을 모르므로 애초에 도메인 기반 Primary 판정 대상이 될 수 "
                 "없다(Evidence Pipeline의 결함이 아니라 Collection 단계의 한계)"),
    }


def check_policy_law_court_primary(claims, documents):
    matches = [
        c for c in claims
        if isinstance(c, dict)
        and c.get("claim_type") in _POLICY_LAW_COURT_CLAIM_TYPES
        and c.get("claim_status") in _PRIMARY_CLAIM_STATUSES
    ]
    return {
        "status": "VERIFIED" if matches else "PENDING",
        "matching_claim_count": len(matches),
        "matching_claim_ids": [c.get("claim_id") for c in matches][:20],
        "diagnosis": _policy_law_court_diagnosis(documents),
    }


def _evidence_pipeline_wired_into_cron():
    """GEMINI_KEY가 이미 daily 워크플로 환경에 존재하는지와 별개로, evidence_pipeline
    자체가 그 워크플로에서 실제로 호출되는지는 완전히 다른 질문이다(읽기 전용 확인만,
    워크플로 파일을 수정하지 않는다 — 섹션 27: 자동 수정 금지)."""
    if not WORKFLOWS_DIR.exists():
        return None
    for f in WORKFLOWS_DIR.glob("*.yml"):
        try:
            text = f.read_text(encoding="utf-8")
        except OSError:
            continue
        if "evidence_pipeline" in text or "intel/pipeline" in text:
            return True
    return False


def check_gemini_level3(claims, metrics):
    level3_claims = [c for c in claims if isinstance(c, dict) and c.get("extraction_method") == "LEVEL3_GEMINI_CANDIDATE"]
    gemini_calls_added = (metrics or {}).get("gemini_calls_added", 0)
    verified = bool(level3_claims) or bool(gemini_calls_added)
    wired = _evidence_pipeline_wired_into_cron()
    return {
        "status": "VERIFIED" if verified else "PENDING",
        "level3_claim_count": len(level3_claims),
        "gemini_calls_added_last_run": gemini_calls_added,
        "evidence_pipeline_wired_into_daily_cron": wired,
        "note": (None if wired else
                 "evidence_pipeline가 .github/workflows의 어떤 크론에도 아직 연결되어 있지 "
                 "않다 — GEMINI_KEY 시크릿 자체는 daily.yml 환경에 이미 존재하지만, "
                 "pipeline.py를 실제로 실행하는 단계가 없어 자연 축적이 구조적으로 불가능하다. "
                 "Evidence Pipeline 코드의 결함이 아니라 배포 통합 여부의 문제이며, 이 Watch는 "
                 "그 사실만 보고하고 워크플로를 직접 수정하지 않는다."),
    }


def check_counter_evidence(counter_evidence_records):
    active = _active_entries(counter_evidence_records)
    return {"status": "VERIFIED" if active else "PENDING", "active_count": len(active)}


def check_structural_object(entries_by_id):
    active = _active_entries(_as_list(entries_by_id))
    return {"status": "VERIFIED" if active else "PENDING", "active_count": len(active)}


def compute_validation_watch():
    claims = _as_list(_load_json(EVIDENCE_PIPELINE_DIR / "claims.json", []))
    documents = _as_list(_load_json(INTEL_DIR / "documents.json", []))
    metrics = _load_json(EVIDENCE_PIPELINE_DIR / "evidence_metrics.json", {})
    counter_evidence = _as_list(_load_json(EVIDENCE_PIPELINE_DIR / "evidence_counter.json", []))
    dependencies = _load_json(STRUCTURAL_ANALYSIS_DIR / "dependencies.json", {})
    controls = _load_json(STRUCTURAL_ANALYSIS_DIR / "controls.json", {})

    watch = {
        "policy_law_court_primary": check_policy_law_court_primary(claims, documents),
        "gemini_level3": check_gemini_level3(claims, metrics),
        "counter_evidence": check_counter_evidence(counter_evidence),
        "dependency": check_structural_object(dependencies),
        "control": check_structural_object(controls),
    }
    for v in watch.values():
        assert v["status"] in STATUS_VALUES
    watch["all_verified"] = all(v["status"] == "VERIFIED" for v in watch.values() if isinstance(v, dict) and "status" in v)
    return watch


def run(write_output=True):
    watch = compute_validation_watch()
    if write_output:
        out_path = HERE / "production_validation_watch.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(watch, f, ensure_ascii=False, indent=1, sort_keys=True)
            f.write("\n")
    return watch


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=1))
