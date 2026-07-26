from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4

from pydantic import ValidationError

from nxjob.schemas.core import (
    AiProviderConfigUpdate,
    AiProviderProfileRecord,
    DolCacheDirectoryUpdate,
    MasterResumeProfile,
    SavedAnswerCreate,
    SavedAnswerRecord,
    SavedAnswerUpdate,
    SavedAnswersImportEntry,
    ResumeOutputDirectoryUpdate,
)
from nxjob.storage.paths import app_data_dir


PRIVATE_DIR_NAME = "private"
MASTER_RESUME_FILE = "master-resume.json"
AI_PROVIDER_FILE = "ai-provider.json"
RESUME_OUTPUT_FILE = "resume-output.json"
DOL_CACHE_FILE = "dol-cache.json"
FORM_ANSWER_LIBRARY_FILE = "form-answer-library.v1.json"
FORM_ANSWER_LIBRARY_VERSION = 1
_FORM_ANSWER_LIBRARY_LOCK = Lock()


class PrivateConfigError(RuntimeError):
    pass


class PrivateConfigNotFoundError(PrivateConfigError):
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


def private_form_answer_library_path() -> Path:
    return private_config_dir() / FORM_ANSWER_LIBRARY_FILE


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


def list_saved_answers() -> list[SavedAnswerRecord]:
    with _FORM_ANSWER_LIBRARY_LOCK:
        return _read_form_answer_library_payload()["answers"]


def create_saved_answer(payload: SavedAnswerCreate) -> SavedAnswerRecord:
    with _FORM_ANSWER_LIBRARY_LOCK:
        answers = _read_form_answer_library_payload()["answers"]
        now = _utc_now()
        normalized_question = _normalize_question(payload.question)
        normalized_key = _normalize_question_key(payload.question)
        normalized_answers = _normalize_answers(payload.answers)
        dedupe_key = _saved_answer_dedupe_key(normalized_key, payload.fieldType, normalized_answers)
        existing_index = next(
            (
                index
                for index, current in enumerate(answers)
                if _saved_answer_record_dedupe_key(current) == dedupe_key
            ),
            None,
        )
        if existing_index is None:
            record = SavedAnswerRecord(
                id=f"answer_{uuid4().hex[:12]}",
                question=normalized_question,
                normalizedQuestion=normalized_key,
                fieldType=payload.fieldType,
                answers=normalized_answers,
                sensitive=payload.sensitive,
                createdAt=now,
                updatedAt=now,
                lastUsedAt=now,
            )
            answers.insert(0, record)
        else:
            existing = answers[existing_index]
            record = existing.model_copy(
                update={
                    "question": normalized_question,
                    "sensitive": payload.sensitive,
                    "updatedAt": now,
                    "lastUsedAt": now,
                }
            )
            answers[existing_index] = record
        _write_form_answer_library_payload(answers)
        return record


def update_saved_answer(answer_id: str, payload: SavedAnswerUpdate) -> SavedAnswerRecord:
    with _FORM_ANSWER_LIBRARY_LOCK:
        answers = _read_form_answer_library_payload()["answers"]
        index = _find_saved_answer_index(answers, answer_id)
        existing = answers[index]
        now = _utc_now()
        updated = existing.model_copy(
            update={
                "answers": _normalize_answers(payload.answers),
                "sensitive": existing.sensitive if payload.sensitive is None else payload.sensitive,
                "updatedAt": now,
                "lastUsedAt": now,
            }
        )
        answers[index] = updated
        _write_form_answer_library_payload(answers)
        return updated


def touch_saved_answer(answer_id: str) -> SavedAnswerRecord:
    with _FORM_ANSWER_LIBRARY_LOCK:
        answers = _read_form_answer_library_payload()["answers"]
        index = _find_saved_answer_index(answers, answer_id)
        touched = answers[index].model_copy(update={"lastUsedAt": _utc_now()})
        answers[index] = touched
        _write_form_answer_library_payload(answers)
        return touched


def delete_saved_answer(answer_id: str) -> None:
    with _FORM_ANSWER_LIBRARY_LOCK:
        answers = _read_form_answer_library_payload()["answers"]
        index = _find_saved_answer_index(answers, answer_id)
        del answers[index]
        _write_form_answer_library_payload(answers)


def clear_saved_answers() -> None:
    path = private_form_answer_library_path()
    with _FORM_ANSWER_LIBRARY_LOCK:
        if path.exists():
            path.unlink()


def import_saved_answers(entries: list[SavedAnswersImportEntry]) -> list[SavedAnswerRecord]:
    with _FORM_ANSWER_LIBRARY_LOCK:
        answers = _read_form_answer_library_payload()["answers"]
        for entry in entries:
            normalized_question = _normalize_question(entry.question)
            normalized_key = _normalize_question_key(entry.question)
            normalized_answers = _normalize_answers(entry.answers)
            dedupe_key = _saved_answer_dedupe_key(normalized_key, entry.fieldType, normalized_answers)
            existing_index = next(
                (
                    index
                    for index, current in enumerate(answers)
                    if _saved_answer_record_dedupe_key(current) == dedupe_key
                ),
                None,
            )
            existing = answers[existing_index] if existing_index is not None else None
            record = SavedAnswerRecord(
                id=existing.id if existing is not None else f"answer_{uuid4().hex[:12]}",
                question=normalized_question,
                normalizedQuestion=normalized_key,
                fieldType=entry.fieldType,
                answers=normalized_answers,
                sensitive=(existing.sensitive if existing is not None else False) or entry.sensitive,
                createdAt=_earliest_timestamp(
                    entry.createdAt,
                    existing.createdAt if existing is not None else "",
                ),
                updatedAt=_latest_timestamp(
                    entry.updatedAt,
                    existing.updatedAt if existing is not None else "",
                    entry.createdAt,
                    existing.createdAt if existing is not None else "",
                ),
                lastUsedAt=_latest_timestamp(
                    entry.lastUsedAt,
                    entry.updatedAt,
                    existing.lastUsedAt if existing is not None else "",
                    existing.updatedAt if existing is not None else "",
                    entry.createdAt,
                    existing.createdAt if existing is not None else "",
                ),
            )
            if existing_index is None:
                answers.append(record)
            else:
                answers[existing_index] = record
        _write_form_answer_library_payload(answers)
        return answers


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


def _read_form_answer_library_payload() -> dict[str, object]:
    path = private_form_answer_library_path()
    if not path.exists():
        return {"version": FORM_ANSWER_LIBRARY_VERSION, "answers": []}

    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise PrivateConfigError("Saved answers file is unreadable.") from exc

    if not isinstance(data, dict):
        raise PrivateConfigError("Saved answers file is unreadable.")

    try:
        version = int(data.get("version", FORM_ANSWER_LIBRARY_VERSION))
    except (TypeError, ValueError) as exc:
        raise PrivateConfigError("Saved answers file is unreadable.") from exc
    if version != FORM_ANSWER_LIBRARY_VERSION:
        raise PrivateConfigError("Saved answers file is unreadable.")

    raw_answers = data.get("answers", [])
    if not isinstance(raw_answers, list):
        raise PrivateConfigError("Saved answers file is unreadable.")

    try:
        answers = [SavedAnswerRecord.model_validate(item) for item in raw_answers]
    except ValidationError as exc:
        raise PrivateConfigError("Saved answers file is unreadable.") from exc
    return {"version": version, "answers": answers}


def _write_form_answer_library_payload(answers: list[SavedAnswerRecord]) -> None:
    path = private_form_answer_library_path()
    _ensure_private_dir(path.parent)
    payload = {
        "version": FORM_ANSWER_LIBRARY_VERSION,
        "answers": [answer.model_dump() for answer in answers],
    }
    _atomic_write_private_json(path, payload)


def _atomic_write_private_json(path: Path, data: dict[str, object]) -> None:
    tmp_path = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
    try:
        tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        if os.name != "nt":
            tmp_path.chmod(0o600)
        tmp_path.replace(path)
    except OSError as exc:
        raise PrivateConfigError("Saved answers file could not be written.") from exc
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def _normalize_question(value: str) -> str:
    return " ".join(value.split()).strip()


def _normalize_question_key(value: str) -> str:
    normalized = _normalize_question(value).lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return " ".join(normalized.split()).strip()


def _normalize_answers(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = " ".join(str(value).split()).strip()
        if not clean or clean in seen:
            continue
        normalized.append(clean)
        seen.add(clean)
    if not normalized:
        raise PrivateConfigError("Saved answers must include at least one non-empty value.")
    return normalized


def _find_saved_answer_index(answers: list[SavedAnswerRecord], answer_id: str) -> int:
    for index, answer in enumerate(answers):
        if answer.id == answer_id:
            return index
    raise PrivateConfigNotFoundError("Saved answer was not found.")


def _first_timestamp(*values: str) -> str:
    for value in values:
        if str(value).strip():
            return str(value).strip()
    return _utc_now()


def _earliest_timestamp(*values: str) -> str:
    return _select_timestamp(min, *values)


def _latest_timestamp(*values: str) -> str:
    return _select_timestamp(max, *values)


def _select_timestamp(selector, *values: str) -> str:
    parsed: list[tuple[datetime, str]] = []
    for value in values:
        clean = str(value).strip()
        if not clean:
            continue
        parsed.append((_parse_timestamp(clean), clean))
    if not parsed:
        return _utc_now()
    return selector(parsed, key=lambda item: item[0])[1]


def _parse_timestamp(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    return datetime.fromisoformat(normalized)


def _saved_answer_dedupe_key(normalized_question: str, field_type: str, answers: list[str]) -> tuple[str, str, tuple[str, ...]]:
    return (normalized_question, field_type, tuple(answers))


def _saved_answer_record_dedupe_key(record: SavedAnswerRecord) -> tuple[str, str, tuple[str, ...]]:
    return _saved_answer_dedupe_key(record.normalizedQuestion, record.fieldType, record.answers)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
