from __future__ import annotations

import json
from urllib.error import HTTPError

import pytest

from nxjob.ai.openai_compatible import AiProviderError, request_json_object
from nxjob.ai.openai_compatible import _chat_completions_endpoint
from nxjob.settings.private_config import AiProviderConfig


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_openai_compatible_client_reads_json_object(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["authorization"] = request.get_header("Authorization")
        captured["timeout"] = timeout
        return FakeResponse(
            {
                "model": "test-model",
                "usage": {"total_tokens": 42},
                "choices": [{"message": {"content": "{\"ok\": true}"}}],
            }
        )

    monkeypatch.setattr("nxjob.ai.openai_compatible.urlopen", fake_urlopen)

    result = request_json_object(
        AiProviderConfig(
            provider="openai_compatible",
            base_url="https://api.example.test/v1",
            model="test-model",
            api_key="test-api-key-secret",
        ),
        [{"role": "user", "content": "Return JSON."}],
    )

    assert result.data == {"ok": True}
    assert result.token_usage["total_tokens"] == 42
    assert captured["url"] == "https://api.example.test/v1/chat/completions"
    assert captured["authorization"] == "Bearer test-api-key-secret"


@pytest.mark.parametrize(
    ("provider", "base_url", "endpoint"),
    [
        ("openai", "", "https://api.openai.com/v1/chat/completions"),
        ("openai", "https://api.openai.com", "https://api.openai.com/v1/chat/completions"),
        ("openai", "https://api.openai.com/v1", "https://api.openai.com/v1/chat/completions"),
        ("deepseek", "", "https://api.deepseek.com/v1/chat/completions"),
        ("deepseek", "https://api.deepseek.com", "https://api.deepseek.com/v1/chat/completions"),
        ("deepseek_v4_flash", "", "https://api.deepseek.com/v1/chat/completions"),
        ("deepseek_v4_pro", "", "https://api.deepseek.com/v1/chat/completions"),
        ("gemini", "", "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"),
        (
            "gemini",
            "https://generativelanguage.googleapis.com",
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        ),
        (
            "gemini_grounded",
            "",
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        ),
        ("openrouter", "", "https://openrouter.ai/api/v1/chat/completions"),
        ("openrouter", "https://openrouter.ai", "https://openrouter.ai/api/v1/chat/completions"),
        ("custom", "https://llm.example.test/v1/chat/completions", "https://llm.example.test/v1/chat/completions"),
    ],
)
def test_chat_completions_endpoint_normalizes_common_provider_base_urls(
    provider,
    base_url,
    endpoint,
) -> None:
    assert _chat_completions_endpoint(base_url, provider) == endpoint


@pytest.mark.parametrize(
    ("provider", "expected_model"),
    [
        ("deepseek", "deepseek-v4-flash"),
        ("deepseek_v4_flash", "deepseek-v4-flash"),
        ("deepseek_v4_pro", "deepseek-v4-pro"),
        ("gemini", "gemini-2.5-flash-lite"),
        ("gemini_grounded", "gemini-2.5-flash"),
    ],
)
def test_openai_compatible_client_uses_provider_default_models(
    monkeypatch,
    provider,
    expected_model,
) -> None:
    captured = {}

    def fake_urlopen(request, timeout):
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse(
            {
                "model": expected_model,
                "usage": {},
                "choices": [{"message": {"content": "{\"ok\": true}"}}],
            }
        )

    monkeypatch.setattr("nxjob.ai.openai_compatible.urlopen", fake_urlopen)

    request_json_object(
        AiProviderConfig(
            provider=provider,
            base_url="",
            model="",
            api_key="test-api-key-secret",
        ),
        [{"role": "user", "content": "Return JSON."}],
    )

    assert captured["payload"]["model"] == expected_model


@pytest.mark.parametrize(
    ("status_code", "category", "public_status"),
    [
        (401, "authentication_failed", 401),
        (429, "rate_limited", 429),
        (404, "endpoint_not_found", 502),
        (503, "provider_unavailable", 502),
    ],
)
def test_openai_compatible_client_classifies_http_errors(
    monkeypatch,
    status_code,
    category,
    public_status,
) -> None:
    def fake_urlopen(request, timeout):
        raise HTTPError(request.full_url, status_code, "error", hdrs=None, fp=None)

    monkeypatch.setattr("nxjob.ai.openai_compatible.urlopen", fake_urlopen)

    with pytest.raises(AiProviderError) as exc:
        request_json_object(
            AiProviderConfig(
                provider="openai_compatible",
                base_url="https://api.example.test/v1",
                model="test-model",
                api_key="test-api-key-secret",
            ),
            [{"role": "user", "content": "Return JSON."}],
        )

    assert exc.value.category == category
    assert exc.value.status_code == public_status
    assert exc.value.upstream_status == status_code
    assert "test-api-key-secret" not in exc.value.user_message


def test_openai_compatible_client_explains_retryable_provider_unavailable(monkeypatch) -> None:
    def fake_urlopen(request, timeout):
        raise HTTPError(request.full_url, 503, "unavailable", hdrs=None, fp=None)

    monkeypatch.setattr("nxjob.ai.openai_compatible.urlopen", fake_urlopen)

    with pytest.raises(AiProviderError) as exc:
        request_json_object(
            AiProviderConfig(
                provider="gemini",
                base_url="",
                model="gemini-2.5-flash-lite",
                api_key="test-api-key-secret",
            ),
            [{"role": "user", "content": "Return JSON."}],
        )

    assert exc.value.category == "provider_unavailable"
    assert exc.value.retryable is True
    assert exc.value.upstream_status == 503
    assert "HTTP 503" in exc.value.user_message
