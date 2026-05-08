from __future__ import annotations

from fastapi import APIRouter, HTTPException

from nxjob.core.trace import new_trace_id
from nxjob.schemas.core import (
    AiProviderConfigUpdate,
    ConfigStatusResponse,
    MasterResumeConfigUpdate,
)
from nxjob.settings.private_config import (
    PrivateConfigError,
    delete_ai_provider_config,
    read_ai_provider_status,
    read_master_resume_status,
    save_ai_provider_config,
    save_master_resume,
)

router = APIRouter(prefix="/api/v1/config", tags=["config"])


@router.get("/status", response_model=ConfigStatusResponse)
def read_config_status() -> ConfigStatusResponse:
    master_configured, master_source, _master_path = read_master_resume_status()
    ai_configured, ai_provider, ai_model = read_ai_provider_status()
    warnings: list[str] = []

    if not master_configured:
        warnings.append("Master Resume is not configured.")
    if not ai_configured:
        warnings.append("AI provider is not configured.")

    return ConfigStatusResponse(
        trace_id=new_trace_id(),
        master_resume_configured=master_configured,
        master_resume_source=master_source,
        ai_provider_configured=ai_configured,
        ai_provider_name=ai_provider if ai_configured else "",
        ai_model=ai_model if ai_configured else "",
        public_lookup_available=False,
        warnings=warnings,
    )


@router.post("/master-resume", response_model=ConfigStatusResponse)
def update_master_resume_config(payload: MasterResumeConfigUpdate) -> ConfigStatusResponse:
    try:
        save_master_resume(payload.content)
    except PrivateConfigError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return read_config_status()


@router.post("/ai-provider", response_model=ConfigStatusResponse)
def update_ai_provider_config(payload: AiProviderConfigUpdate) -> ConfigStatusResponse:
    try:
        save_ai_provider_config(payload)
    except PrivateConfigError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return read_config_status()


@router.delete("/ai-provider", response_model=ConfigStatusResponse)
def clear_ai_provider_config() -> ConfigStatusResponse:
    delete_ai_provider_config()
    return read_config_status()
