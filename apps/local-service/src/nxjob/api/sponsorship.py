from __future__ import annotations

from fastapi import APIRouter, HTTPException

from nxjob.core.trace import new_trace_id
from nxjob.db.connection import db_session
from nxjob.db.repositories import (
    create_sponsorship_evidence,
    create_workflow_trace,
    get_job_lead,
    utc_now,
)
from nxjob.schemas.core import (
    SponsorshipAnalyzeRequest,
    SponsorshipAnalyzeResponse,
    WorkflowTraceRecord,
)
from nxjob.workflows.sponsorship_analyzer import WORKFLOW_NAME, analyze_sponsorship

router = APIRouter(prefix="/api/v1/sponsorship", tags=["sponsorship"])


@router.post("/analyze", response_model=SponsorshipAnalyzeResponse)
def analyze_sponsorship_endpoint(payload: SponsorshipAnalyzeRequest) -> SponsorshipAnalyzeResponse:
    trace_id = new_trace_id()

    with db_session() as connection:
        try:
            job_lead = get_job_lead(connection, payload.job_lead_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="JobLead not found") from exc

        jd_text = payload.jd_text or job_lead.jd_text
        if not jd_text:
            raise HTTPException(status_code=422, detail="jd_text or JobLead.jd_text is required")

        analysis = analyze_sponsorship(payload, jd_text).model_copy(update={"trace_id": trace_id})
        create_workflow_trace(
            connection,
            WorkflowTraceRecord(
                trace_id=trace_id,
                workflow_name=WORKFLOW_NAME,
                created_at=utc_now(),
                input_summary=f"job_lead_id={payload.job_lead_id}; allow_ai={payload.allow_ai}",
                output_summary=analysis.sponsorship.status,
                status="completed",
            ),
        )
        create_sponsorship_evidence(connection, payload.job_lead_id, trace_id, analysis)

    return analysis
