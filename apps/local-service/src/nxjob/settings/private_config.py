from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from nxjob.schemas.core import (
    AiProviderConfigUpdate,
    AiProviderProfileRecord,
    DolCacheDirectoryUpdate,
    MasterResumeProfile,
    ResumeOutputDirectoryUpdate,
)
from nxjob.storage.paths import app_data_dir


PRIVATE_DIR_NAME = "private"
MASTER_RESUME_FILE = "master-resume.json"
AI_PROVIDER_FILE = "ai-provider.json"
RESUME_OUTPUT_FILE = "resume-output.json"
DOL_CACHE_FILE = "dol-cache.json"


class PrivateConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class AiProviderConfig:
    provider: str
    base_url: str
    model: str
    api_key: str
    profile_id: str = ""
    display_name: str = ""
    reasoning_effort: str = "medium"


def private_config_dir() -> Path:
    return app_data_dir() / PRIVATE_DIR_NAME


def private_master_resume_path() -> Path:
    return private_config_dir() / MASTER_RESUME_FILE


def private_ai_provider_path() -> Path:
    return private_config_dir() / AI_PROVIDER_FILE


def private_resume_output_path() -> Path:
    return private_config_dir() / RESUME_OUTPUT_FILE


def private_dol_cache_path() -> Path:
    return private_config_dir() / DOL_CACHE_FILE


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
    profile_id = _new_profile_id()
    display_name = payload.display_name.strip() or _default_profile_name(provider, payload.model)
    data = {
        "active_profile_id": profile_id,
        "profiles": [
            {
                "id": profile_id,
                "display_name": display_name,
                "provider": provider,
                "base_url": payload.base_url.strip(),
                "model": payload.model.strip(),
                "api_key": api_key,
                "reasoning_effort": _normalize_reasoning_effort(payload.reasoning_effort),
            }
        ],
    }
    path = private_ai_provider_path()
    existing = _read_private_ai_provider_data()
    if existing is not None:
        profiles = [profile for profile in existing.get("profiles", []) if isinstance(profile, dict)]
        profiles = [profile for profile in profiles if profile.get("id") != profile_id]
        profiles.insert(0, data["profiles"][0])
        data["profiles"] = profiles
    _ensure_private_dir(path.parent)
    _write_private_json(path, data)


def delete_ai_provider_config() -> None:
    path = private_ai_provider_path()
    if path.exists():
        path.unlink()


def read_ai_provider_status() -> tuple[bool, str, str, str, str, str, str]:
    private_config = _read_private_ai_provider_config()
    if private_config is not None:
        return (
            True,
            private_config.provider,
            private_config.model,
            private_config.reasoning_effort,
            private_config.profile_id,
            private_config.display_name,
            "private_config",
        )

    env_config = _read_env_ai_provider_config()
    if env_config is not None:
        return (
            True,
            env_config.provider,
            env_config.model,
            env_config.reasoning_effort,
            env_config.profile_id,
            env_config.display_name,
            "environment",
        )

    return False, "", "", "", "", "", ""


def list_ai_provider_profiles() -> tuple[list[AiProviderProfileRecord], str]:
    data = _read_private_ai_provider_data()
    if data is None:
        env_config = _read_env_ai_provider_config()
        if env_config is None:
            return [], ""
        return [
            AiProviderProfileRecord(
                id=env_config.profile_id,
                display_name=env_config.display_name,
                provider=env_config.provider,
                base_url=env_config.base_url,
                model=env_config.model,
                reasoning_effort=env_config.reasoning_effort,
                source="environment",
                is_active=True,
            )
        ], env_config.profile_id

    active_profile_id = str(data.get("active_profile_id", "")).strip()
    profiles: list[AiProviderProfileRecord] = []
    for profile in data.get("profiles", []):
        if not isinstance(profile, dict):
            continue
        profile_id = str(profile.get("id", "")).strip()
        provider = _normalize_provider(str(profile.get("provider", "")))
        api_key = str(profile.get("api_key", "")).strip()
        if not profile_id or not provider or not api_key:
            continue
        profiles.append(
            AiProviderProfileRecord(
                id=profile_id,
                display_name=str(profile.get("display_name", "")).strip() or _default_profile_name(provider, str(profile.get("model", ""))),
                provider=provider,
                base_url=str(profile.get("base_url", "")).strip(),
                model=str(profile.get("model", "")).strip(),
                reasoning_effort=_normalize_reasoning_effort(str(profile.get("reasoning_effort", "medium"))),
                source="private_config",
                is_active=profile_id == active_profile_id,
            )
        )
    return profiles, active_profile_id


def activate_ai_provider_profile(profile_id: str) -> AiProviderProfileRecord:
    data = _read_private_ai_provider_data()
    if data is None:
        raise PrivateConfigError("AI provider profile was not found.")

    profiles, _active_id = list_ai_provider_profiles()
    matched = next((profile for profile in profiles if profile.id == profile_id), None)
    if matched is None:
        raise PrivateConfigError("AI provider profile was not found.")

    data["active_profile_id"] = profile_id
    _write_private_json(private_ai_provider_path(), data)
    return matched.model_copy(update={"is_active": True})


def delete_ai_provider_profile(profile_id: str) -> None:
    data = _read_private_ai_provider_data()
    if data is None:
        return

    profiles = [profile for profile in data.get("profiles", []) if isinstance(profile, dict) and profile.get("id") != profile_id]
    if not profiles:
        delete_ai_provider_config()
        return

    active_profile_id = str(data.get("active_profile_id", "")).strip()
    if active_profile_id == profile_id:
        data["active_profile_id"] = str(profiles[0].get("id", "")).strip()
    data["profiles"] = profiles
    _write_private_json(private_ai_provider_path(), data)


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
        profile_id="env",
        display_name=_default_profile_name(os.environ.get("NXJOB_AI_PROVIDER", "openai"), os.environ.get("NXJOB_AI_MODEL", "")),
        provider=_normalize_provider(os.environ.get("NXJOB_AI_PROVIDER", "openai")),
        base_url=os.environ.get("NXJOB_AI_BASE_URL", "").strip(),
        model=os.environ.get("NXJOB_AI_MODEL", "").strip(),
        api_key=env_api_key,
        reasoning_effort=_normalize_reasoning_effort(os.environ.get("NXJOB_AI_REASONING_EFFORT", "medium")),
    )


def _read_private_ai_provider_config() -> AiProviderConfig | None:
    data = _read_private_ai_provider_data()
    if data is None:
        return None

    active_profile_id = str(data.get("active_profile_id", "")).strip()
    profiles = [profile for profile in data.get("profiles", []) if isinstance(profile, dict)]
    active_profile = next((profile for profile in profiles if str(profile.get("id", "")).strip() == active_profile_id), None)
    if active_profile is None and profiles:
        active_profile = profiles[0]
    if active_profile is None:
        return None

    api_key = str(active_profile.get("api_key", "")).strip()
    if not api_key:
        return None

    provider = _normalize_provider(str(active_profile.get("provider", "")))
    model = str(active_profile.get("model", "")).strip()
    return AiProviderConfig(
        profile_id=str(active_profile.get("id", "")).strip(),
        display_name=str(active_profile.get("display_name", "")).strip() or _default_profile_name(provider, model),
        provider=provider,
        base_url=str(active_profile.get("base_url", "")).strip(),
        model=model,
        api_key=api_key,
        reasoning_effort=_normalize_reasoning_effort(str(active_profile.get("reasoning_effort", "medium"))),
    )


def _read_private_ai_provider_data() -> dict[str, object] | None:
    path = private_ai_provider_path()
    if not path.exists():
        return None

    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(data, dict):
        return None
    if "profiles" in data:
        return data

    api_key = str(data.get("api_key", "")).strip()
    provider = _normalize_provider(str(data.get("provider", "")))
    if not api_key or not provider:
        return None
    profile_id = _new_profile_id()
    return {
        "active_profile_id": profile_id,
        "profiles": [
            {
                "id": profile_id,
                "display_name": _default_profile_name(provider, str(data.get("model", ""))),
                "provider": provider,
                "base_url": str(data.get("base_url", "")).strip(),
                "model": str(data.get("model", "")).strip(),
                "api_key": api_key,
                "reasoning_effort": _normalize_reasoning_effort(str(data.get("reasoning_effort", "medium"))),
            }
        ],
    }


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


def configured_dol_cache_dir() -> Path:
    configured = os.environ.get("NXJOB_DOL_CACHE_DIR")
    if configured:
        return Path(configured).expanduser()

    path = private_dol_cache_path()
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            data = {}
        configured_path = str(data.get("path", "")).strip() if isinstance(data, dict) else ""
        if configured_path:
            return Path(configured_path).expanduser()

    return app_data_dir() / "cache" / "dol-lca"


def read_dol_cache_status() -> tuple[bool, str, str]:
    configured = os.environ.get("NXJOB_DOL_CACHE_DIR")
    if configured:
        return True, "environment", str(Path(configured).expanduser())

    path = private_dol_cache_path()
    if path.exists():
        return True, "private_config", str(configured_dol_cache_dir())

    return False, "default", str(configured_dol_cache_dir())


def read_dol_max_cache_bytes() -> int:
    configured = os.environ.get("NXJOB_DOL_MAX_CACHE_BYTES")
    if configured:
        return _parse_positive_int(configured, 2 * 1024 * 1024 * 1024)

    path = private_dol_cache_path()
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            data = {}
        if isinstance(data, dict) and data.get("max_cache_bytes") is not None:
            return _parse_positive_int(str(data.get("max_cache_bytes")), 2 * 1024 * 1024 * 1024)

    return 2 * 1024 * 1024 * 1024


def save_dol_cache_dir(payload: DolCacheDirectoryUpdate) -> Path:
    raw_path = payload.path.strip()
    if not raw_path:
        raise PrivateConfigError("DOL cache folder is required.")

    path = Path(raw_path).expanduser()
    _validate_dol_cache_path(path)
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".nxjob-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        raise PrivateConfigError(f"DOL cache folder is not writable: {path}") from exc

    config_path = private_dol_cache_path()
    _ensure_private_dir(config_path.parent)
    data: dict[str, object] = {"path": str(path)}
    if payload.max_cache_bytes is not None:
        data["max_cache_bytes"] = payload.max_cache_bytes
    elif config_path.exists():
        existing = _read_private_json(config_path)
        if existing.get("max_cache_bytes") is not None:
            data["max_cache_bytes"] = existing["max_cache_bytes"]
    _write_private_json(config_path, data)
    return path


def _validate_dol_cache_path(path: Path) -> None:
    parts = {part.lower() for part in path.parts}
    if "extension" in parts or "localservice" in parts:
        raise PrivateConfigError("DOL cache folder cannot be inside extension or LocalService install directories.")


def _ensure_private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _write_private_json(path: Path, data: dict[str, object]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    if os.name != "nt":
        path.chmod(0o600)


def _read_private_json(path: Path) -> dict[str, object]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _parse_positive_int(value: str, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _normalize_provider(provider: str) -> str:
    value = provider.strip().lower()
    aliases = {
        "": "openai",
        "openai_compatible": "openai",
        "openai-compatible": "openai",
        "chatgpt": "openai",
        "deepseek": "deepseek",
        "deepseek_v4_flash": "deepseek_v4_flash",
        "deepseek-v4-flash": "deepseek_v4_flash",
        "deepseek_flash": "deepseek_v4_flash",
        "deepseek-flash": "deepseek_v4_flash",
        "deepseek_v4_pro": "deepseek_v4_pro",
        "deepseek-v4-pro": "deepseek_v4_pro",
        "deepseek_pro": "deepseek_v4_pro",
        "deepseek-pro": "deepseek_v4_pro",
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


def _normalize_reasoning_effort(reasoning_effort: str) -> str:
    value = reasoning_effort.strip().lower().replace("-", "_")
    return value if value in {"none", "minimal", "low", "medium", "high"} else "medium"


def _default_profile_name(provider: str, model: str) -> str:
    normalized_provider = _normalize_provider(provider)
    clean_model = model.strip()
    return f"{normalized_provider} / {clean_model}" if clean_model else normalized_provider


def _new_profile_id() -> str:
    return f"aip_{uuid4().hex[:12]}"
