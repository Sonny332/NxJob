from __future__ import annotations

from fastapi import APIRouter, HTTPException

from nxjob.core.trace import new_trace_id
from nxjob.db.connection import db_session
from nxjob.db.repositories import create_resume_version, get_resume_version
from nxjob.schemas.core import ResumeVersionCreate, ResumeVersionRecord, ResumeVersionResponse

router = APIRouter(prefix="/api/v1/resume-versions", tags=["resume-versions"])


@router.post("", response_model=ResumeVersionResponse)
def create_resume_version_endpoint(payload: ResumeVersionCreate) -> ResumeVersionResponse:
    trace_id = new_trace_id()
    with db_session() as connection:
        try:
            record = create_resume_version(connection, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Referenced record not found") from exc

    return ResumeVersionResponse(trace_id=trace_id, resume_version=record)


@router.get("/{resume_version_id}", response_model=ResumeVersionRecord)
def read_resume_version(resume_version_id: str) -> ResumeVersionRecord:
    with db_session() as connection:
        try:
            return get_resume_version(connection, resume_version_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="ResumeVersion not found") from exc

