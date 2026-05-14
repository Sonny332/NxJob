from __future__ import annotations

from fastapi import APIRouter, HTTPException

from nxjob.core.trace import new_trace_id
from nxjob.core.workflow_cache import workflow_cache_key
from nxjob.ai.openai_compatible import AiProviderError
from nxjob.db.connection import db_session
from nxjob.db.repositories import (
    create_prompt_log,
    create_sponsorship_evidence,
    create_workflow_trace,
    create_workflow_result,
    find_cached_workflow_result,
    get_job_lead,
    utc_now,
)
from nxjob.schemas.core import (
    PromptLogCreate,
    SponsorshipAnalyzeRequest,
    SponsorshipAnalyzeResponse,
    WorkflowCacheInfo,
    WorkflowTraceRecord,
)
from nxjob.settings.private_config import read_ai_provider_config, read_ai_provider_status
from nxjob.workflows.sponsorship_analyzer import (
    WORKFLOW_NAME,
    add_ai_unavailable_evidence,
    analyze_sponsorship,
    analyze_sponsorship_with_ai,
)

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
            "v2",
            {
                "jd_hash": job_lead.jd_hash,
                "application_form_text": payload.application_form_text,
                "allow_public_lookup": payload.allow_public_lookup,
                "allow_ai": payload.allow_ai,
                "ai_provider": _ai_cache_identity() if payload.allow_ai else "disabled",
            },
        )
        if not payload.force_refresh:
            cached = find_cached_workflow_result(connection, WORKFLOW_NAME, cache_key)
            if cached is not None:
                return SponsorshipAnalyzeResponse.model_validate(cached.response).model_copy(
                    update={"cache": WorkflowCacheInfo(hit=True, cache_key=cache_key)}
                )

        trace_id = new_trace_id()
        analysis = analyze_sponsorship(payload, jd_text)
        ai_config = read_ai_provider_config() if _should_use_ai(payload, analysis) else None
        (
            _ai_configured,
            _ai_provider_name,
            _ai_model,
            _ai_reasoning_effort,
            _ai_profile_id,
            _ai_profile_display_name,
            ai_provider_source,
        ) = read_ai_provider_status()
        prompt_log_payload: PromptLogCreate | None = None
        if _should_use_ai(payload, analysis):
            if ai_config is None:
                analysis = add_ai_unavailable_evidence(analysis)
            else:
                try:
                    ai_result = analyze_sponsorship_with_ai(payload, jd_text, analysis, ai_config)
                    analysis = ai_result.response
                    prompt_log_payload = PromptLogCreate(
                        trace_id=trace_id,
                        workflow_name=WORKFLOW_NAME,
                        input_summary="JD sponsorship indicators only; full JD not logged",
                        model=ai_result.model,
                        provider=ai_result.provider,
                        token_usage=ai_result.token_usage,
                        output_summary=analysis.sponsorship.status,
                    )
                except AiProviderError as exc:
                    analysis = add_ai_unavailable_evidence(analysis, exc)
                    prompt_log_payload = PromptLogCreate(
                        trace_id=trace_id,
                        workflow_name=WORKFLOW_NAME,
                        input_summary="JD sponsorship indicators only; full JD not logged",
                        model=ai_config.model,
                        provider=ai_config.provider,
                        token_usage={},
                        output_summary="",
                        error=f"{exc.category}; source={ai_provider_source}",
                    )

        analysis = analysis.model_copy(
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
        if prompt_log_payload is not None:
            create_prompt_log(connection, prompt_log_payload)
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


def _should_use_ai(payload: SponsorshipAnalyzeRequest, analysis: SponsorshipAnalyzeResponse) -> bool:
    return payload.allow_ai and analysis.sponsorship.status in {"needs_confirmation", "unknown"}


def _ai_cache_identity() -> dict[str, str]:
    config = read_ai_provider_config()
    if config is None:
        return {"provider": "not_configured", "model": ""}
    return {"provider": config.provider, "model": config.model}
