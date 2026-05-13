from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from nxjob.schemas.core import AiProviderConfigUpdate, MasterResumeProfile, ResumeOutputDirectoryUpdate
from nxjob.storage.paths import app_data_dir


PRIVATE_DIR_NAME = "private"
MASTER_RESUME_FILE = "master-resume.json"
AI_PROVIDER_FILE = "ai-provider.json"
RESUME_OUTPUT_FILE = "resume-output.json"


class PrivateConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class AiProviderConfig:
    provider: str
    base_url: str
    model: str
    api_key: str


def private_config_dir() -> Path:
    return app_data_dir() / PRIVATE_DIR_NAME


def private_master_resume_path() -> Path:
    return private_config_dir() / MASTER_RESUME_FILE


def private_ai_provider_path() -> Path:
    return private_config_dir() / AI_PROVIDER_FILE


def private_resume_output_path() -> Path:
    return private_config_dir() / RESUME_OUTPUT_FILE


def configured_master_resume_path() -> Path | None:
    configured = os.environ.get("NXJOB_MASTER_RESUME_PATH")
    if configured:
        return Path(configured)

    private_path = private_master_resume_path()
    return private_path if private_path.exists() else None


def save_master_resume(content: str) -> MasterResumeProfile:
    try:
        data = json.loads(content)
        profile = MasterResumeProfile.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise PrivateConfigError("Master resume must be valid NxJob JSON.") from exc

    path = private_master_resume_path()
    _ensure_private_dir(path.parent)
    _write_private_json(path, profile.model_dump())
    return profile


def read_master_resume_status() -> tuple[bool, str, str]:
    configured = os.environ.get("NXJOB_MASTER_RESUME_PATH")
    if configured:
        path = Path(configured)
        return path.exists(), "environment", str(path) if path.exists() else ""

    path = private_master_resume_path()
    return path.exists(), "private_config" if path.exists() else "", str(path) if path.exists() else ""


def save_ai_provider_config(payload: AiProviderConfigUpdate) -> None:
    api_key = payload.api_key.strip()
    if not api_key:
        raise PrivateConfigError("AI API key is required.")

    provider = _normalize_provider(payload.provider)
    data = {
        "provider": provider,
        "base_url": payload.base_url.strip(),
        "model": payload.model.strip(),
        "api_key": api_key,
    }
    path = private_ai_provider_path()
    _ensure_private_dir(path.parent)
    _write_private_json(path, data)


def delete_ai_provider_config() -> None:
    path = private_ai_provider_path()
    if path.exists():
        path.unlink()


def read_ai_provider_status() -> tuple[bool, str, str, str]:
    private_config = _read_private_ai_provider_config()
    if private_config is not None:
        return True, private_config.provider, private_config.model, "private_config"

    env_config = _read_env_ai_provider_config()
    if env_config is not None:
        return True, env_config.provider, env_config.model, "environment"

    return False, "", "", ""


def read_ai_provider_config() -> AiProviderConfig | None:
    private_config = _read_private_ai_provider_config()
    if private_config is not None:
        return private_config

    return _read_env_ai_provider_config()


def _read_env_ai_provider_config() -> AiProviderConfig | None:
    env_api_key = os.environ.get("NXJOB_AI_API_KEY", "").strip()
    if not env_api_key:
        return None

    return AiProviderConfig(
        provider=_normalize_provider(os.environ.get("NXJOB_AI_PROVIDER", "openai")),
        base_url=os.environ.get("NXJOB_AI_BASE_URL", "").strip(),
        model=os.environ.get("NXJOB_AI_MODEL", "").strip(),
        api_key=env_api_key,
    )


def _read_private_ai_provider_config() -> AiProviderConfig | None:
    path = private_ai_provider_path()
    if not path.exists():
        return None

    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None

    api_key = str(data.get("api_key", "")).strip()
    if not api_key:
        return None

    return AiProviderConfig(
        provider=_normalize_provider(str(data.get("provider", ""))),
        base_url=str(data.get("base_url", "")).strip(),
        model=str(data.get("model", "")).strip(),
        api_key=api_key,
    )


def configured_resume_output_dir() -> Path | None:
    configured = os.environ.get("NXJOB_GENERATED_RESUME_DIR")
    if configured:
        return Path(configured)

    path = private_resume_output_path()
    if not path.exists():
        return None

    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None

    configured_path = str(data.get("path", "")).strip()
    return Path(configured_path) if configured_path else None


def read_resume_output_status() -> tuple[bool, str, str]:
    configured = os.environ.get("NXJOB_GENERATED_RESUME_DIR")
    if configured:
        path = Path(configured)
        return path.exists(), "environment", str(path) if path.exists() else str(path)

    path = configured_resume_output_dir()
    if path is None:
        return False, "", ""

    return path.exists(), "private_config" if path.exists() else "", str(path)


def save_resume_output_dir(payload: ResumeOutputDirectoryUpdate) -> Path:
    raw_path = payload.path.strip()
    if not raw_path:
        raise PrivateConfigError("Resume output folder is required.")

    path = Path(raw_path).expanduser()
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".nxjob-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        raise PrivateConfigError(f"Resume output folder is not writable: {path}") from exc

    config_path = private_resume_output_path()
    _ensure_private_dir(config_path.parent)
    _write_private_json(config_path, {"path": str(path)})
    return path


def _ensure_private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _write_private_json(path: Path, data: dict[str, object]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    if os.name != "nt":
        path.chmod(0o600)


def _normalize_provider(provider: str) -> str:
    value = provider.strip().lower()
    aliases = {
        "": "openai",
        "openai_compatible": "openai",
        "openai-compatible": "openai",
        "chatgpt": "openai",
        "deepseek": "deepseek",
        "gemini": "gemini",
        "google": "gemini",
        "google_gemini": "gemini",
        "gemini_grounded": "gemini_grounded",
        "gemini-grounded": "gemini_grounded",
        "gemini_search": "gemini_grounded",
        "gemini-search": "gemini_grounded",
        "openrouter": "openrouter",
        "custom": "custom",
    }
    return aliases.get(value, value)
