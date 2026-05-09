from __future__ import annotations

import json
from urllib.error import HTTPError

import pytest

from nxjob.ai.openai_compatible import AiProviderError, request_json_object
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
            api_key="sk-secret",
        ),
        [{"role": "user", "content": "Return JSON."}],
    )

    assert result.data == {"ok": True}
    assert result.token_usage["total_tokens"] == 42
    assert captured["url"] == "https://api.example.test/v1/chat/completions"
    assert captured["authorization"] == "Bearer sk-secret"


@pytest.mark.parametrize(
    ("status_code", "category", "public_status"),
    [
        (401, "authentication_failed", 401),
        (429, "rate_limited", 429),
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
                api_key="sk-secret",
            ),
            [{"role": "user", "content": "Return JSON."}],
        )

    assert exc.value.category == category
    assert exc.value.status_code == public_status
    assert "sk-secret" not in exc.value.user_message
