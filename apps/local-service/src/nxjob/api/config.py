from __future__ import annotations

from fastapi import APIRouter, HTTPException

from nxjob.core.trace import new_trace_id
from nxjob.schemas.core import (
    AiProviderConfigUpdate,
    ConfigStatusResponse,
    MasterResumeConfigUpdate,
    ResumeOutputDirectoryUpdate,
)
from nxjob.settings.private_config import (
    PrivateConfigError,
    delete_ai_provider_config,
    read_ai_provider_status,
    read_master_resume_status,
    read_resume_output_status,
    save_ai_provider_config,
    save_master_resume,
    save_resume_output_dir,
)

router = APIRouter(prefix="/api/v1/config", tags=["config"])


@router.get("/status", response_model=ConfigStatusResponse)
def read_config_status() -> ConfigStatusResponse:
    master_configured, master_source, _master_path = read_master_resume_status()
    ai_configured, ai_provider, ai_model = read_ai_provider_status()
    output_configured, _output_source, output_dir = read_resume_output_status()
    warnings: list[str] = []

    if not master_configured:
        warnings.append("Master Resume is not configured.")
    if not ai_configured:
        warnings.append("AI provider is not configured.")
    if not output_configured:
        warnings.append("Resume output folder is not configured.")

    return ConfigStatusResponse(
        trace_id=new_trace_id(),
        master_resume_configured=master_configured,
        master_resume_source=master_source,
        ai_provider_configured=ai_configured,
        ai_provider_name=ai_provider if ai_configured else "",
        ai_model=ai_model if ai_configured else "",
        resume_output_dir_configured=output_configured,
        resume_output_dir=output_dir,
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


@router.post("/resume-output-directory", response_model=ConfigStatusResponse)
def update_resume_output_directory(payload: ResumeOutputDirectoryUpdate) -> ConfigStatusResponse:
    try:
        save_resume_output_dir(payload)
    except PrivateConfigError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return read_config_status()
