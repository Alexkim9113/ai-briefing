# STAGE 6 — SUBSTEP C: Adapter(섹션 2, 6). 기존 Stage 1-5 산출물을 READ-ONLY로만 읽는다.
# 이 파일은 어떤 기존 파일도 절대 쓰지 않는다 — 여기서 로드한 dict/list는 이 프로세스
# 메모리 안에서만 존재하고, 원본 JSON 파일은 전혀 수정되지 않는다.
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INTEL_DIR = HERE.parent


def _load(path, default):
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return default
    if isinstance(default, list) and isinstance(data, dict):
        return list(data.values())
    return data


def load_documents():
    """document_id -> document. Provenance lineage의 최종 종착점(섹션 11)."""
    docs = _load(INTEL_DIR / "documents.json", [])
    return {d["document_id"]: d for d in docs if isinstance(d, dict) and "document_id" in d}


def load_facts_verified():
    """evidence_pipeline/facts_verified.json — FACT 계열의 실제 Production 소스."""
    return _load(INTEL_DIR / "evidence_pipeline" / "facts_verified.json", [])


def load_production_events():
    """event_production/production_events.json — EVENT 계열의 실제 Production 소스."""
    return _load(INTEL_DIR / "event_production" / "production_events.json", [])


def load_changes():
    """change_layer/changes.json — CHANGE 계열. override_status가 HUMAN_REJECTED인
    항목은 atomizer가 제외해야 한다(섹션 38: Human override는 rerun으로 덮어쓰지 않는다 —
    거부된 것을 지식으로 승격시키지 않는다는 뜻도 포함)."""
    return _load(INTEL_DIR / "change_layer" / "changes.json", [])


def load_evidence_records():
    """evidence_pipeline/evidence_records.json — Counter Evidence/구조적 후보(BOTTLENECK/
    DRIVER 등)의 원천. 이번 Foundation은 이 객체들을 Atomic Note로 직접 승격하지 않는다
    (전부 claim_status가 INSUFFICIENT_SOURCE/SECONDARY_ONLY로 약하거나 HUMAN_REJECTED임 —
    섹션 62: 없는/약한 Insight를 억지로 만들지 않는다). 다만 향후 supporting/counter
    evidence 연결에 쓸 수 있도록 읽기는 제공한다.
    """
    return _load(INTEL_DIR / "evidence_pipeline" / "evidence_records.json", [])


def load_evidence_overrides():
    return _load(INTEL_DIR / "evidence_pipeline" / "evidence_pipeline_overrides.json", {})


def audit_summary():
    """SUBSTEP A: 현재 각 Stage 산출물에 실제로 몇 건이 있는지 — Knowledge Memory가
    참조할 수 있는 실제 재료가 무엇인지 정직하게 집계한다(추측 없음)."""
    facts = load_facts_verified()
    events = load_production_events()
    changes = load_changes()
    evidence = load_evidence_records()
    active_changes = [c for c in changes if c.get("override_status") != "HUMAN_REJECTED"]
    return {
        "facts_verified": len(facts),
        "production_events": len(events),
        "changes_total": len(changes),
        "changes_active_non_rejected": len(active_changes),
        "changes_human_rejected": len(changes) - len(active_changes),
        "evidence_records": len(evidence),
        "documents": len(load_documents()),
        # 아래는 실제 corpus에서 아직 0건인 상위 Interpretive 객체들 — 억지로 채우지 않고
        # 있는 그대로 보고한다(섹션 73-74).
        "note": ("Interpretive 계열(QUESTION/HYPOTHESIS/INSIGHT/POLICY_IDEA/RESEARCH_IDEA)에 "
                 "대응하는 기존 Stage 객체(policy_questions.json/research_questions.json/"
                 "scenarios.json/forecasts.json 등)는 현재 corpus에서 전부 0건이다 — 이는 "
                 "Knowledge Memory의 결함이 아니라 그 상위 layer들이 아직 실제 데이터를 "
                 "만들어내지 못한 상태이며, 이번 Foundation은 그것을 대신 채우지 않는다."),
    }
