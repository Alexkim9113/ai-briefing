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

HERE = Path(__file__).resolve().parent
INTEL_DIR = HERE.parent
EVIDENCE_PIPELINE_DIR = INTEL_DIR / "evidence_pipeline"
STRUCTURAL_ANALYSIS_DIR = INTEL_DIR / "structural_analysis_layer"

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


def check_policy_law_court_primary(claims):
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
    }


def check_gemini_level3(claims, metrics):
    level3_claims = [c for c in claims if isinstance(c, dict) and c.get("extraction_method") == "LEVEL3_GEMINI_CANDIDATE"]
    gemini_calls_added = (metrics or {}).get("gemini_calls_added", 0)
    verified = bool(level3_claims) or bool(gemini_calls_added)
    return {
        "status": "VERIFIED" if verified else "PENDING",
        "level3_claim_count": len(level3_claims),
        "gemini_calls_added_last_run": gemini_calls_added,
    }


def check_counter_evidence(counter_evidence_records):
    active = _active_entries(counter_evidence_records)
    return {"status": "VERIFIED" if active else "PENDING", "active_count": len(active)}


def check_structural_object(entries_by_id):
    active = _active_entries(_as_list(entries_by_id))
    return {"status": "VERIFIED" if active else "PENDING", "active_count": len(active)}


def compute_validation_watch():
    claims = _as_list(_load_json(EVIDENCE_PIPELINE_DIR / "claims.json", []))
    metrics = _load_json(EVIDENCE_PIPELINE_DIR / "evidence_metrics.json", {})
    counter_evidence = _as_list(_load_json(EVIDENCE_PIPELINE_DIR / "evidence_counter.json", []))
    dependencies = _load_json(STRUCTURAL_ANALYSIS_DIR / "dependencies.json", {})
    controls = _load_json(STRUCTURAL_ANALYSIS_DIR / "controls.json", {})

    watch = {
        "policy_law_court_primary": check_policy_law_court_primary(claims),
        "gemini_level3": check_gemini_level3(claims, metrics),
        "counter_evidence": check_counter_evidence(counter_evidence),
        "dependency": check_structural_object(dependencies),
        "control": check_structural_object(controls),
    }
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
