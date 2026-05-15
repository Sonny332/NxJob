from __future__ import annotations

from fastapi import APIRouter, HTTPException

from nxjob.core.trace import new_trace_id
from nxjob.db.connection import db_session
from nxjob.db.repositories import create_application, get_application, list_applications_for_job
from nxjob.schemas.core import ApplicationCreate, ApplicationListResponse, ApplicationRecord, ApplicationResponse

router = APIRouter(prefix="/api/v1/applications", tags=["applications"])


@router.post("", response_model=ApplicationResponse)
def create_application_endpoint(payload: ApplicationCreate) -> ApplicationResponse:
    trace_id = new_trace_id()
    with db_session() as connection:
        try:
            record = create_application(connection, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Referenced record not found") from exc

    return ApplicationResponse(trace_id=trace_id, application=record)


@router.get("", response_model=ApplicationListResponse)
def list_applications(job_lead_id: str = "", limit: int = 20) -> ApplicationListResponse:
    trace_id = new_trace_id()
    with db_session() as connection:
        applications = (
            list_applications_for_job(connection, job_lead_id, max(1, min(limit, 100)))
            if job_lead_id
            else []
        )
    return ApplicationListResponse(trace_id=trace_id, applications=applications)


@router.get("/{application_id}", response_model=ApplicationRecord)
def read_application(application_id: str) -> ApplicationRecord:
    with db_session() as connection:
        try:
            return get_application(connection, application_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Application not found") from exc

