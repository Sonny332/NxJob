from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from nxjob.settings.private_config import AiProviderConfig


DEFAULT_BASE_URL = "https://api.openai.com/v1"


@dataclass(frozen=True)
class AiJsonResult:
    data: dict[str, Any]
    token_usage: dict[str, Any]
    model: str
    provider: str


class AiProviderError(RuntimeError):
    def __init__(self, category: str, user_message: str, status_code: int = 502) -> None:
        super().__init__(user_message)
        self.category = category
        self.user_message = user_message
        self.status_code = status_code


def request_json_object(
    config: AiProviderConfig,
    messages: list[dict[str, str]],
    timeout_seconds: int = 60,
) -> AiJsonResult:
    model = config.model.strip()
    if not model:
        raise AiProviderError("invalid_config", "AI model is not configured.", 422)
    if not config.api_key.strip():
        raise AiProviderError("missing_key", "AI API key is not configured.", 422)

    endpoint = _chat_completions_endpoint(config.base_url)
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise _http_error(exc) from exc
    except URLError as exc:
        raise AiProviderError("network_error", "AI provider network request failed.") from exc
    except TimeoutError as exc:
        raise AiProviderError("network_timeout", "AI provider request timed out.") from exc
    except json.JSONDecodeError as exc:
        raise AiProviderError("invalid_response", "AI provider returned invalid JSON.") from exc

    content = _message_content(response_data)
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise AiProviderError("invalid_response", "AI provider did not return a JSON object.") from exc

    if not isinstance(data, dict):
        raise AiProviderError("invalid_response", "AI provider returned an invalid JSON payload.")

    return AiJsonResult(
        data=data,
        token_usage=response_data.get("usage", {}) if isinstance(response_data, dict) else {},
        model=str(response_data.get("model", model)) if isinstance(response_data, dict) else model,
        provider=config.provider or "openai_compatible",
    )


def _chat_completions_endpoint(base_url: str) -> str:
    normalized = (base_url.strip() or DEFAULT_BASE_URL).rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    return f"{normalized}/chat/completions"


def _message_content(response_data: dict[str, Any]) -> str:
    choices = response_data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise AiProviderError("invalid_response", "AI provider response did not include choices.")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise AiProviderError("invalid_response", "AI provider response did not include content.")
    return content


def _http_error(exc: HTTPError) -> AiProviderError:
    if exc.code in {401, 403}:
        return AiProviderError("authentication_failed", "AI provider authentication failed.", 401)
    if exc.code == 429:
        return AiProviderError("rate_limited", "AI provider rate limit was reached.", 429)
    if 500 <= exc.code <= 599:
        return AiProviderError("provider_unavailable", "AI provider is temporarily unavailable.", 502)
    return AiProviderError("provider_error", f"AI provider returned HTTP {exc.code}.", 502)
