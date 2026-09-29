# STAGE 7 PHASE H — synthetic tests (섹션 62): two-pass Deep Think, anti-summary guard,
# anti-generic-insight guard, Claude failure fallback. 실제 네트워크 호출 없음(injected client).
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))

import deep_think  # noqa: E402
from schema import new_context_pack_shell  # noqa: E402


class _FakeUsage:
    input_tokens = 100
    output_tokens = 50


class _FakeBlock:
    def __init__(self, text):
        self.text = text


class _FakeResponse:
    def __init__(self, text):
        self.content = [_FakeBlock(text)]
        self.usage = _FakeUsage()


def _client_with_response(text):
    class _Messages:
        def create(self, **kwargs):
            return _FakeResponse(text)

    class _Client:
        def __init__(self):
            self.messages = _Messages()

    return lambda: _Client()


def _sample_context_pack():
    pack = new_context_pack_shell()
    pack["known_facts"] = [{"note_id": "n1", "statement": "AI Agent 사용이 증가했다"}]
    pack["object_references"] = ["n1"]
    return pack


def test_pass1_returns_configured_status_with_injected_client():
    result = deep_think.run_pass1(_sample_context_pack(), "질문", {"claim_ceiling": "OBSERVED_FACT", "state": "SUFFICIENT_FOR_FACT_LOOKUP"},
                                   client_factory=_client_with_response(json.dumps({"question": "q"})))
    assert result["status"] == "CONFIGURED"


def test_deep_think_full_flow_with_injected_client():
    pack = _sample_context_pack()
    suff = {"claim_ceiling": "OBSERVED_CHANGE", "state": "SUFFICIENT_FOR_DESCRIPTIVE_ANALYSIS"}
    result = deep_think.run_deep_think(pack, "질문", suff, client_factory=_client_with_response("synthesis text citing n1"))
    assert result["status"] == "COMPLETE"
    assert result["pass1"] and result["pass2"]
    assert result["guard"] is not None


def test_deep_think_falls_back_when_claude_not_configured():
    import os
    old = os.environ.pop("ANTHROPIC_API_KEY", None)
    try:
        pack = _sample_context_pack()
        suff = {"claim_ceiling": "OBSERVED_FACT", "state": "SUFFICIENT_FOR_FACT_LOOKUP"}
        result = deep_think.run_deep_think(pack, "질문", suff, client_factory=None)
        assert result["status"] == "RETRIEVAL_ONLY_FALLBACK"
    finally:
        if old is not None:
            os.environ["ANTHROPIC_API_KEY"] = old


def test_deep_think_guard_flags_no_evidence_cited():
    pack = new_context_pack_shell()  # object_references 비어있음
    suff = {"claim_ceiling": "OBSERVED_FACT", "state": "SUFFICIENT_FOR_FACT_LOOKUP"}
    result = deep_think.run_deep_think(pack, "질문", suff, client_factory=_client_with_response("어떤 근거도 인용하지 않은 답"))
    assert result["status"] == "COMPLETE"
    assert result["guard"]["passed"] is False
    assert any("NO_EVIDENCE_CITED" in f for f in result["guard"]["findings"])


def test_deep_think_guard_flags_generic_convergence():
    pack = _sample_context_pack()
    suff = {"claim_ceiling": "OBSERVED_CHANGE", "state": "SUFFICIENT_FOR_DESCRIPTIVE_ANALYSIS"}
    result = deep_think.run_deep_think(pack, "질문", suff,
                                        client_factory=_client_with_response("결국 인간의 판단이 중요해지고 있다 [n1]"))
    assert result["guard"]["passed"] is False
    assert any("GENERIC_CONCLUSION_DETECTED" in f for f in result["guard"]["findings"])
