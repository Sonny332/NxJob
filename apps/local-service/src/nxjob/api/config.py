from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException

from nxjob.core.trace import new_trace_id
from nxjob.data.dol_lca_index_manager import get_dol_index_status
from nxjob.schemas.core import (
    AiProviderProfileActivateResponse,
    AiProviderProfilesResponse,
    AiProviderConfigUpdate,
    ConfigStatusResponse,
    DolCacheDirectoryUpdate,
    DolIndexStatusSummary,
    MasterResumeConfigUpdate,
    ResumeOutputDirectoryUpdate,
)
from nxjob.settings.private_config import (
    PrivateConfigError,
    activate_ai_provider_profile,
    delete_ai_provider_config,
    delete_ai_provider_profile,
    list_ai_provider_profiles,
    read_dol_cache_status,
    read_ai_provider_status,
    read_master_resume_status,
    read_resume_output_status,
    save_ai_provider_config,
    save_dol_cache_dir,
    save_master_resume,
    save_resume_output_dir,
)

router = APIRouter(prefix="/api/v1/config", tags=["config"])


@router.get("/status", response_model=ConfigStatusResponse)
def read_config_status() -> ConfigStatusResponse:
    master_configured, master_source, _master_path = read_master_resume_status()
    (
        ai_configured,
        ai_provider,
        ai_model,
        ai_reasoning_effort,
        ai_profile_id,
        ai_profile_display_name,
        ai_provider_source,
    ) = read_ai_provider_status()
    output_configured, _output_source, output_dir = read_resume_output_status()
    dol_cache_configured, dol_cache_source, dol_cache_dir = read_dol_cache_status()
    dol_index_status = DolIndexStatusSummary.model_validate(asdict(get_dol_index_status(check_remote=False)))
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
        ai_reasoning_effort=ai_reasoning_effort if ai_configured else "",
        ai_profile_id=ai_profile_id if ai_configured else "",
        ai_profile_display_name=ai_profile_display_name if ai_configured else "",
        ai_provider_source=ai_provider_source if ai_configured else "",
        resume_output_dir_configured=output_configured,
        resume_output_dir=output_dir,
        dol_cache_dir_configured=dol_cache_configured,
        dol_cache_dir_source=dol_cache_source,
        dol_cache_dir=dol_cache_dir,
        public_lookup_available=True,
        dol_index_status=dol_index_status,
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


@router.get("/ai-profiles", response_model=AiProviderProfilesResponse)
def read_ai_provider_profiles() -> AiProviderProfilesResponse:
    profiles, active_profile_id = list_ai_provider_profiles()
    return AiProviderProfilesResponse(
        trace_id=new_trace_id(),
        profiles=profiles,
        active_profile_id=active_profile_id,
    )


@router.post("/ai-profiles/{profile_id}/activate", response_model=AiProviderProfileActivateResponse)
def activate_ai_profile(profile_id: str) -> AiProviderProfileActivateResponse:
    try:
        profile = activate_ai_provider_profile(profile_id)
    except PrivateConfigError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AiProviderProfileActivateResponse(trace_id=new_trace_id(), profile=profile)


@router.delete("/ai-profiles/{profile_id}", response_model=ConfigStatusResponse)
def delete_ai_profile(profile_id: str) -> ConfigStatusResponse:
    delete_ai_provider_profile(profile_id)
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


@router.post("/dol-cache-directory", response_model=ConfigStatusResponse)
def update_dol_cache_directory(payload: DolCacheDirectoryUpdate) -> ConfigStatusResponse:
    try:
        save_dol_cache_dir(payload)
    except PrivateConfigError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return read_config_status()
