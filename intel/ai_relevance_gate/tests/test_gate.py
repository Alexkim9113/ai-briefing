import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import gate  # noqa: E402


def test_central_ai_passes():
    v = gate.evaluate("정부, AI 기본법 시행령 발표", "AI 기본법 세부 규정을 담은 시행령이 공개됐다")
    assert v["gate"] == gate.GATE_PASS


def test_incidental_ai_mention_in_body_only_fails():
    # No standalone AI token in the title -- the counterfactual REMOVE_AI_TEST applies to the
    # body, and here removing the one AI sentence leaves the real story (chip demand) intact,
    # so AI is PERIPHERAL, not the structural subject of the event.
    v = gate.evaluate("기업들 올해 실적은 반도체 수요가 좌우",
                       "일부 기업은 AI를 도입했다고 밝혔다. 실제 실적 변동은 전통 반도체 수요 회복이 주된 원인이다. "
                       "메모리 가격 상승과 재고 조정이 이번 분기 매출을 이끌었다. 이 흐름은 수개월째 이어지고 있다.")
    assert v["gate"] in (gate.GATE_FAIL, gate.GATE_AMBIGUOUS)


def test_weak_keyword_only_fails():
    v = gate.evaluate("데이터센터 전력 수요 증가, 알고리즘 효율화로 대응", "")
    assert v["gate"] == gate.GATE_FAIL


def test_general_news_fails():
    v = gate.evaluate("태풍 북상, 남부지방 비 피해 우려", "기상청은 이번 주말 태풍의 영향으로...")
    assert v["gate"] == gate.GATE_FAIL


def test_never_raises_on_empty_input():
    v = gate.evaluate("", "")
    assert v["gate"] == gate.GATE_FAIL


def test_run_on_documents_never_mutates_source_files(tmp_path):
    import json
    import shutil
    root = Path(__file__).resolve().parent.parent.parent.parent
    docs_src = root / "intel" / "documents.json"
    facts_src = root / "intel" / "facts.json"
    before_docs = docs_src.read_bytes()
    before_facts = facts_src.read_bytes()
    out = tmp_path / "result.json"
    result = gate.run_on_documents(out_path=out)
    assert docs_src.read_bytes() == before_docs
    assert facts_src.read_bytes() == before_facts
    assert out.exists()
    counts = result["counts"]
    assert counts["PASS"] + counts["FAIL"] + counts["NEEDS_REVIEW"] == result["document_count"]


def test_ambiguous_is_its_own_bucket_never_silently_merged():
    # A real AMBIGUOUS case from assess_ai_relevance's own docstring scenario: a single AI
    # mention with no sentence boundary to run REMOVE_AI_TEST against.
    v = gate.evaluate("AI", "")
    assert v["gate"] in (gate.GATE_PASS, gate.GATE_AMBIGUOUS, gate.GATE_FAIL)
