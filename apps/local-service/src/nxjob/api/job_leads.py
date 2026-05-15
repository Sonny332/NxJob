from __future__ import annotations

from fastapi import APIRouter, HTTPException

from nxjob.core.trace import new_trace_id
from nxjob.db.connection import db_session
from nxjob.db.repositories import create_job_lead, get_job_lead, list_workflow_results_for_job
from nxjob.schemas.core import (
    JobLeadCapture,
    JobLeadCaptureResponse,
    JobLeadRecord,
    WorkflowResultsResponse,
)

router = APIRouter(prefix="/api/v1/job-leads", tags=["job-leads"])


@router.post("/capture", response_model=JobLeadCaptureResponse)
def capture_job_lead(payload: JobLeadCapture) -> JobLeadCaptureResponse:
    if not (payload.selected_text or payload.page_text_excerpt):
        raise HTTPException(status_code=422, detail="selected_text or page_text_excerpt is required")

    trace_id = new_trace_id()
    with db_session() as connection:
        record, duplicate_id = create_job_lead(connection, payload)

    return JobLeadCaptureResponse(
        trace_id=trace_id,
        job_lead=record,
        dedupe={
            "is_duplicate": duplicate_id is not None,
            "existing_job_lead_id": duplicate_id,
        },
    )


@router.get("/{job_lead_id}", response_model=JobLeadRecord)
def read_job_lead(job_lead_id: str) -> JobLeadRecord:
    with db_session() as connection:
        try:
            return get_job_lead(connection, job_lead_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="JobLead not found") from exc


@router.get("/{job_lead_id}/workflow-results", response_model=WorkflowResultsResponse)
def read_job_workflow_results(job_lead_id: str) -> WorkflowResultsResponse:
    with db_session() as connection:
        try:
            get_job_lead(connection, job_lead_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="JobLead not found") from exc

        return WorkflowResultsResponse(
            trace_id=new_trace_id(),
            results=list_workflow_results_for_job(connection, job_lead_id),
        )

