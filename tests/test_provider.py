"""
Offline tests for the model-provider layer.

The OpenAI-compatible provider is exercised by replacing
``urllib.request.urlopen`` so no network access or API key is needed.
"""

import io
import json
from urllib import error as urllib_error

import pytest

from app.models import provider as provider_module
from app.models.provider import (
    MockModelProvider,
    OpenAICompatibleProvider,
    create_model_provider,
)


class _FakeHTTPResponse:

    def __init__(self, payload, status=200):

        self._body = (
            payload
            if isinstance(payload, bytes)
            else json.dumps(payload).encode("utf-8")
        )

        self.status = status

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _provider(**overrides):

    kwargs = dict(
        api_key="test-key",
        model_name="test-model",
        base_url="https://llm.example/v1/",
        provider_name="openrouter",
    )

    kwargs.update(overrides)

    return OpenAICompatibleProvider(**kwargs)


def _patch_urlopen(monkeypatch, behaviour):

    captured = {}

    def fake_urlopen(http_request, timeout=None):

        captured["request"] = http_request
        captured["timeout"] = timeout

        if isinstance(behaviour, Exception):
            raise behaviour

        return behaviour

    monkeypatch.setattr(
        provider_module.urllib_request, "urlopen", fake_urlopen
    )

    return captured


# ---------------------------------------------------------
# Factory
# ---------------------------------------------------------

def test_factory_returns_mock_provider():

    assert isinstance(
        create_model_provider(provider="mock"), MockModelProvider
    )


@pytest.mark.parametrize("name", ["openrouter", "openai", " OpenAI "])
def test_factory_returns_openai_compatible_provider(name):

    created = create_model_provider(provider=name)

    assert isinstance(created, OpenAICompatibleProvider)
    assert created.provider_name == name.strip().lower()


def test_factory_rejects_unknown_provider():

    with pytest.raises(ValueError, match="Unsupported MODEL_PROVIDER"):
        create_model_provider(provider="skynet")


# ---------------------------------------------------------
# OpenAI-compatible provider
# ---------------------------------------------------------

def test_endpoint_is_normalised():

    assert (
        _provider().endpoint
        == "https://llm.example/v1/chat/completions"
    )


def test_missing_api_key_fails_fast(monkeypatch):

    captured = _patch_urlopen(monkeypatch, _FakeHTTPResponse({}))

    with pytest.raises(RuntimeError, match="MODEL_API_KEY"):
        _provider(api_key="").generate("hi")

    assert "request" not in captured


def test_successful_generation_maps_response(monkeypatch):

    captured = _patch_urlopen(
        monkeypatch,
        _FakeHTTPResponse({
            "id": "resp-1",
            "model": "served-model",
            "choices": [
                {
                    "message": {"content": "Paris"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 7,
                "completion_tokens": 3,
                "cost": 0.0004,
            },
        }),
    )

    result = _provider().generate("Capital of France?")

    assert result["text"] == "Paris"
    assert result["input_tokens"] == 7
    assert result["output_tokens"] == 3
    assert result["cost"] == pytest.approx(0.0004)
    assert result["model"] == "served-model"
    assert result["provider"] == "openrouter"
    assert result["metadata"]["total_tokens"] == 10
    assert result["metadata"]["finish_reason"] == "stop"

    sent = captured["request"]
    body = json.loads(sent.data)

    assert body["messages"] == [
        {"role": "user", "content": "Capital of France?"}
    ]
    assert sent.get_header("Authorization") == "Bearer test-key"
    assert sent.get_header("X-title") == "ControlPlane.ai"


def test_missing_usage_does_not_invent_cost(monkeypatch):

    _patch_urlopen(
        monkeypatch,
        _FakeHTTPResponse({"choices": [{"message": {"content": "ok"}}]}),
    )

    result = _provider().generate("hi")

    assert result["cost"] == 0.0
    assert result["input_tokens"] == 0
    assert result["output_tokens"] == 0


def test_http_error_is_wrapped(monkeypatch):

    error = urllib_error.HTTPError(
        url="https://llm.example",
        code=429,
        msg="Too Many Requests",
        hdrs=None,
        fp=io.BytesIO(b'{"error":"slow down"}'),
    )

    _patch_urlopen(monkeypatch, error)

    with pytest.raises(RuntimeError, match=r"HTTP 429.*slow down"):
        _provider().generate("hi")


def test_connection_error_is_wrapped(monkeypatch):

    _patch_urlopen(
        monkeypatch, urllib_error.URLError("name resolution failed")
    )

    with pytest.raises(RuntimeError, match="Unable to connect"):
        _provider().generate("hi")


def test_timeout_is_wrapped(monkeypatch):

    _patch_urlopen(monkeypatch, TimeoutError())

    with pytest.raises(RuntimeError, match="timed out"):
        _provider().generate("hi")


def test_invalid_json_is_rejected(monkeypatch):

    _patch_urlopen(monkeypatch, _FakeHTTPResponse(b"<html>oops</html>"))

    with pytest.raises(RuntimeError, match="invalid JSON"):
        _provider().generate("hi")


def test_empty_choices_is_rejected(monkeypatch):

    _patch_urlopen(monkeypatch, _FakeHTTPResponse({"choices": []}))

    with pytest.raises(RuntimeError, match="Unable to extract"):
        _provider().generate("hi")


def test_non_list_non_string_messages_rejected():

    with pytest.raises(TypeError):
        _provider().generate(42)
