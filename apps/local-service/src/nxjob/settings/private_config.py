from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import ValidationError

from nxjob.schemas.core import AiProviderConfigUpdate, MasterResumeProfile
from nxjob.storage.paths import app_data_dir


PRIVATE_DIR_NAME = "private"
MASTER_RESUME_FILE = "master-resume.json"
AI_PROVIDER_FILE = "ai-provider.json"


class PrivateConfigError(RuntimeError):
    pass


def private_config_dir() -> Path:
    return app_data_dir() / PRIVATE_DIR_NAME


def private_master_resume_path() -> Path:
    return private_config_dir() / MASTER_RESUME_FILE


def private_ai_provider_path() -> Path:
    return private_config_dir() / AI_PROVIDER_FILE


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

    data = {
        "provider": payload.provider.strip() or "openai_compatible",
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


def read_ai_provider_status() -> tuple[bool, str, str]:
    path = private_ai_provider_path()
    if not path.exists():
        return False, "", ""

    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return False, "", ""

    configured = bool(str(data.get("api_key", "")).strip())
    return configured, str(data.get("provider", "")), str(data.get("model", ""))


def _ensure_private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _write_private_json(path: Path, data: dict[str, object]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    if os.name != "nt":
        path.chmod(0o600)
