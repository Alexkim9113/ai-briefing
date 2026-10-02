import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import candidate_engine as ce  # noqa: E402


def test_field_remap_uses_o3c_vocabulary():
    for old_field in ("기술", "법·규제", "의료", "노동·경제", "에너지·환경", "안보",
                       "AI정책·국제질서", "문화·사회"):
        mapped = ce._o3c_field(old_field)
        assert mapped is None or mapped in (
            "기술", "산업·경제", "노동·고용", "법·제도", "의료·헬스케어", "에너지·환경",
            "국방·안보", "교육·사회", "문화·예술", "미디어·콘텐츠", "정책·국제질서",
        )


def test_candidate_never_creates_claim_or_hypothesis_or_io():
    result = ce.detect_candidates()
    # The only status this module is allowed to emit for a passing issue.
    for c in result.get("candidates", []):
        assert c["status"] == "INTELLIGENCE_CANDIDATE"
        assert "claim_id" not in c
        assert "hypothesis_id" not in c
        assert "intelligence_object_id" not in c


def test_priority_and_evidence_quality_never_merged():
    result = ce.detect_candidates()
    for c in result.get("candidates", []):
        assert "evidence_quality" in c
        assert c["evidence_quality"] == "UNKNOWN"  # never inferred from recurrence alone


def test_research_queue_dedup_on_rerun(tmp_path):
    out = tmp_path / "queue.json"
    candidates = [{
        "candidate_id": "cand_test1", "title": "테스트 이슈", "field": "기술", "region": "KR",
        "recurring_days": 3, "independent_source_count": 2, "related_event_count": 5,
        "tier1_present": False, "related_intelligence_topic": None,
        "evidence_quality": "UNKNOWN", "reason": "테스트", "status": "INTELLIGENCE_CANDIDATE",
    }]
    rows1 = ce.update_research_queue(candidates, out_path=out)
    assert len(rows1) == 1
    first_seen = rows1[0]["first_seen"]

    candidates[0]["related_event_count"] = 9  # same identity, updated count
    rows2 = ce.update_research_queue(candidates, out_path=out)
    assert len(rows2) == 1  # no duplicate row
    assert rows2[0]["first_seen"] == first_seen  # first_seen preserved
    assert rows2[0]["related_events"] == 9  # last_seen data refreshed


def test_research_status_not_reset_on_update(tmp_path):
    out = tmp_path / "queue.json"
    candidates = [{
        "candidate_id": "cand_test2", "title": "테스트", "field": "기술", "region": "US",
        "recurring_days": 2, "independent_source_count": 2, "related_event_count": 3,
        "tier1_present": False, "related_intelligence_topic": None,
        "evidence_quality": "UNKNOWN", "reason": "테스트", "status": "INTELLIGENCE_CANDIDATE",
    }]
    ce.update_research_queue(candidates, out_path=out)
    rows = json.loads(out.read_text(encoding="utf-8"))
    rows[0]["research_status"] = "RESEARCH_IN_PROGRESS"
    out.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

    ce.update_research_queue(candidates, out_path=out)
    rows_after = json.loads(out.read_text(encoding="utf-8"))
    assert rows_after[0]["research_status"] == "RESEARCH_IN_PROGRESS"


def test_run_never_mutates_canonical_files(tmp_path):
    import hashlib
    root = HERE.parent.parent.parent
    paths = [
        root / "intel" / "report_engine" / "reports" / "report_intel_87210a61730c22b9_v4.json",
        root / "intel" / "claims" / "claims.json",
        root / "intel" / "hypothesis" / "hypotheses.json",
        root / "intel" / "intelligence_objects" / "intelligence_objects.json",
    ]
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    ce.run()
    after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    assert before == after


def test_identity_is_stable_across_runs():
    r1 = ce.detect_candidates()
    r2 = ce.detect_candidates()
    ids1 = sorted(c["candidate_id"] for c in r1.get("candidates", []))
    ids2 = sorted(c["candidate_id"] for c in r2.get("candidates", []))
    assert ids1 == ids2
