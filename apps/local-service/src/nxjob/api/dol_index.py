from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException

from nxjob.core.trace import new_trace_id
from nxjob.data.dol_lca_index_manager import (
    cleanup_dol_index_cache,
    get_dol_index_job,
    get_dol_index_status,
    start_dol_index_build,
)
from nxjob.schemas.core import (
    DolIndexBuildRequest,
    DolIndexBuildResponse,
    DolIndexCleanupResponse,
    DolIndexJobResponse,
    DolIndexStatusResponse,
)

router = APIRouter(prefix="/api/v1/dol/index", tags=["dol-index"])


@router.get("/status", response_model=DolIndexStatusResponse)
def read_dol_index_status() -> DolIndexStatusResponse:
    payload = asdict(get_dol_index_status(check_remote=True))
    payload["trace_id"] = new_trace_id()
    return DolIndexStatusResponse.model_validate(payload)


@router.post("/build", response_model=DolIndexBuildResponse)
def build_dol_index(payload: DolIndexBuildRequest) -> DolIndexBuildResponse:
    job = start_dol_index_build(force=payload.force)
    data = asdict(job)
    data["trace_id"] = new_trace_id()
    return DolIndexBuildResponse.model_validate(data)


@router.get("/jobs/{job_id}", response_model=DolIndexJobResponse)
def read_dol_index_job(job_id: str) -> DolIndexJobResponse:
    job = get_dol_index_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="DOL index job not found")
    data = asdict(job)
    data["trace_id"] = new_trace_id()
    return DolIndexJobResponse.model_validate(data)


@router.post("/cleanup", response_model=DolIndexCleanupResponse)
def cleanup_dol_index() -> DolIndexCleanupResponse:
    result = cleanup_dol_index_cache()
    data = asdict(result)
    data["trace_id"] = new_trace_id()
    return DolIndexCleanupResponse.model_validate(data)
