# STAGE 7 PHASE G — synthetic tests (섹션 62): Claude adapter status, failure fallback,
# cache, API key never exposed. 실제 네트워크 호출은 하지 않는다(client_factory로 주입).
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parent
sys.path.insert(0, str(PKG_DIR))

import cache  # noqa: E402
import claude_adapter  # noqa: E402
from prompt_contract import model_for_mode  # noqa: E402


class _FakeUsage:
    def __init__(self, i, o):
        self.input_tokens = i
        self.output_tokens = o


class _FakeBlock:
    def __init__(self, text):
        self.text = text


class _FakeResponse:
    def __init__(self, text):
        self.content = [_FakeBlock(text)]
        self.usage = _FakeUsage(100, 50)


class _FakeMessages:
    def create(self, **kwargs):
        return _FakeResponse(f"analysis of: {kwargs['user']}" if "user" in kwargs else "ok")


class _FakeClient:
    def __init__(self):
        self.messages = self


class _FailingClient:
    class messages:
        @staticmethod
        def create(**kwargs):
            raise ConnectionError("simulated network failure")


def test_no_api_key_reports_not_configured_without_exposing_value():
    import os
    old = os.environ.pop("ANTHROPIC_API_KEY", None)
    try:
        assert claude_adapter.adapter_status() == "NOT_CONFIGURED"
    finally:
        if old is not None:
            os.environ["ANTHROPIC_API_KEY"] = old


def test_call_claude_without_key_returns_not_configured_result():
    import os
    old = os.environ.pop("ANTHROPIC_API_KEY", None)
    try:
        result = claude_adapter.call_claude("sys", "user", "claude-sonnet-5")
        assert result["status"] == "NOT_CONFIGURED"
        assert result["text"] is None
    finally:
        if old is not None:
            os.environ["ANTHROPIC_API_KEY"] = old


def test_call_claude_with_injected_client_succeeds():
    def factory():
        client = _FakeClient()
        client.messages = _FakeMessages()
        return client
    result = claude_adapter.call_claude("sys", "hello", "claude-sonnet-5", client_factory=factory)
    assert result["status"] == "CONFIGURED"
    assert result["text"]
    assert result["usage"]["input_tokens"] == 100


def test_call_claude_failure_falls_back_not_raises():
    result = claude_adapter.call_claude("sys", "hello", "claude-sonnet-5",
                                         client_factory=lambda: _FailingClient())
    assert result["status"] == "CALL_FAILED"
    assert result["text"] is None


def test_model_for_mode_never_hardcodes_in_business_logic():
    # 모델명이 config(prompt_contract.py)에서만 나온다는 것을 확인 - claude_adapter.py
    # 소스코드 자체엔 실제 모델 ID 리터럴이 없어야 한다.
    import inspect
    src = inspect.getsource(claude_adapter)
    assert "claude-sonnet" not in src and "claude-opus" not in src
    assert model_for_mode("ANALYZE")
    assert model_for_mode("DEEP_THINK")


def test_cache_roundtrip():
    cache.put("hash1", "v1", "claude-sonnet-5", {"answer": "cached"})
    assert cache.get("hash1", "v1", "claude-sonnet-5") == {"answer": "cached"}
    assert cache.get("hash1", "v2", "claude-sonnet-5") is None  # 다른 prompt_version은 miss
