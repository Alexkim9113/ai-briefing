# PRODUCTION EVIDENCE SUPPLY v1.0 — SUBSTEP G/H (섹션 20-29, Te 2026-09-29 승인).
# Evidence Pipeline을 실제 Production Workflow(daily.yml)에서 SHADOW 모드로 실행하는
# 진입점. evidence_pipeline/pipeline.py는 한 줄도 수정하지 않는다 — 이미 공개돼 있는
# run(gemini_enabled=, gemini_call_budget=) 인자를 그대로 호출할 뿐이다.
#
# 절대 원칙(섹션 20-24): COLLECTION SUCCESS + PUBLIC SITE SUCCESS + EVIDENCE PIPELINE
# FAILURE가 동시에 가능해야 한다 — 이 스크립트는 별도 GitHub Actions job(daily.yml의
# evidence_shadow job)에서만 실행되고, build job(수집+사이트 생성)과 완전히 분리돼 있어
# Public Site를 절대 막을 수 없다. 그 위에 이 스크립트 자신도 모든 예외를 잡아 항상 exit 0
# 로 끝난다 — Evidence Pipeline 오류가 워크플로 자체를 실패시키지 않게(Fail Closed for
# Evidence, Fail Open for Public), 대신 오류는 감추지 않고 evidence_shadow_run_log.json에
# 기록한다(섹션 55: 오류를 숨기지 않는다).
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
EVIDENCE_PIPELINE_DIR = ROOT / "intel" / "evidence_pipeline"
RUN_LOG_PATH = HERE / "evidence_shadow_run_log.json"

DEFAULT_GEMINI_BUDGET = 15  # pipeline.py의 GEMINI_HARD_CAP_PER_RUN(20) 안쪽의 보수적 기본값


def _env_flag(name, default=False):
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name, default):
    v = os.environ.get(name)
    if not v:
        return default
    try:
        return int(v)
    except ValueError:
        return default


def run():
    now_iso = datetime.now(timezone.utc).isoformat()
    log = {
        "run_at": now_iso,
        "shadow_mode": True,
        "public_site_impact": 0,
        "status": None,
        "gemini_enabled": None,
        "gemini_call_budget": None,
        "reports_on_run": None,
        "pipeline_metrics": None,
        "error": None,
    }

    sys.path.insert(0, str(EVIDENCE_PIPELINE_DIR))
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "intel"))
    sys.path.insert(0, str(ROOT / "intel" / "event_matching"))

    try:
        # SUBSTEP F를 매 실행마다 최신 전체 corpus로 다시 계산(멱등적 — 동일 입력이면
        # 동일 결과, evidence_service.resolve_reports_on의 rel_id가 결정적이라 안전).
        import reports_on_runner
        ror_metrics, _, _ = reports_on_runner.run(write_output=True)
        log["reports_on_run"] = ror_metrics
    except Exception as e:
        log["reports_on_run"] = {"error": str(e)}
        log["error"] = (log["error"] or "") + f"\nreports_on_runner failed: {e}\n{traceback.format_exc()}"

    try:
        import pipeline
        gemini_enabled = _env_flag("EVIDENCE_GEMINI_ENABLED", default=bool(os.environ.get("GEMINI_KEY")))
        gemini_budget = _env_int("EVIDENCE_GEMINI_BUDGET", DEFAULT_GEMINI_BUDGET)
        log["gemini_enabled"] = gemini_enabled
        log["gemini_call_budget"] = gemini_budget
        metrics, *_ = pipeline.run(gemini_enabled=gemini_enabled, gemini_call_budget=gemini_budget)
        log["pipeline_metrics"] = metrics
        log["status"] = "SUCCESS"
    except Exception as e:
        log["status"] = "FAILED"
        log["error"] = (log["error"] or "") + f"\npipeline.run failed: {e}\n{traceback.format_exc()}"

    RUN_LOG_PATH.write_text(json.dumps(log, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return log


if __name__ == "__main__":
    result = run()
    print(json.dumps({k: v for k, v in result.items() if k != "error" or v}, ensure_ascii=False, indent=1))
    # 절대 exit 1로 끝나지 않는다(섹션 55: Evidence 실패가 워크플로를 실패시키면 안 됨).
    sys.exit(0)
