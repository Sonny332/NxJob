from __future__ import annotations

from fastapi import APIRouter, HTTPException

from nxjob.core.trace import new_trace_id
from nxjob.core.workflow_cache import workflow_cache_key
from nxjob.db.connection import db_session
from nxjob.db.repositories import (
    create_sponsorship_evidence,
    create_workflow_trace,
    create_workflow_result,
    find_cached_workflow_result,
    get_job_lead,
    utc_now,
)
from nxjob.schemas.core import (
    SponsorshipAnalyzeRequest,
    SponsorshipAnalyzeResponse,
    WorkflowCacheInfo,
    WorkflowTraceRecord,
)
from nxjob.workflows.sponsorship_analyzer import WORKFLOW_NAME, analyze_sponsorship

router = APIRouter(prefix="/api/v1/sponsorship", tags=["sponsorship"])


@router.post("/analyze", response_model=SponsorshipAnalyzeResponse)
def analyze_sponsorship_endpoint(payload: SponsorshipAnalyzeRequest) -> SponsorshipAnalyzeResponse:
    with db_session() as connection:
        try:
            job_lead = get_job_lead(connection, payload.job_lead_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="JobLead not found") from exc

        jd_text = payload.jd_text or job_lead.jd_text
        if not jd_text:
            raise HTTPException(status_code=422, detail="jd_text or JobLead.jd_text is required")

        cache_key = workflow_cache_key(
            WORKFLOW_NAME,
            "v1",
            {
                "jd_hash": job_lead.jd_hash,
                "application_form_text": payload.application_form_text,
                "allow_public_lookup": payload.allow_public_lookup,
                "allow_ai": payload.allow_ai,
            },
        )
        if not payload.force_refresh:
            cached = find_cached_workflow_result(connection, WORKFLOW_NAME, cache_key)
            if cached is not None:
                return SponsorshipAnalyzeResponse.model_validate(cached.response).model_copy(
                    update={"cache": WorkflowCacheInfo(hit=True, cache_key=cache_key)}
                )

        trace_id = new_trace_id()
        analysis = analyze_sponsorship(payload, jd_text).model_copy(
            update={"trace_id": trace_id, "cache": WorkflowCacheInfo(hit=False, cache_key=cache_key)}
        )
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
        create_workflow_result(
            connection,
            job_lead_id=payload.job_lead_id,
            workflow_name=WORKFLOW_NAME,
            cache_key=cache_key,
            trace_id=trace_id,
            status="completed",
            result_summary=analysis.sponsorship.status,
            response=analysis.model_dump(),
        )

    return analysis
