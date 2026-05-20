from __future__ import annotations

from fastapi import APIRouter, HTTPException

from nxjob.core.trace import new_trace_id
from nxjob.db.connection import db_session
from nxjob.db.repositories import (
    create_form_answer_draft,
    create_prompt_log,
    create_workflow_trace,
    get_job_lead,
    new_id,
    utc_now,
)
from nxjob.resumes.master_resume import MasterResumeNotConfiguredError, load_master_resume
from nxjob.schemas.core import (
    FormAnswerDraftCreate,
    FormAnswerDraftRecord,
    FormAnswerDraftResponse,
    FormAnswerDraftsCreate,
    FormAnswerDraftsResponse,
    PromptLogCreate,
    WorkflowTraceRecord,
)
from nxjob.settings.private_config import read_ai_provider_config
from nxjob.workflows.form_answer_drafter import WORKFLOW_NAME, draft_form_answer

router = APIRouter(prefix="/api/v1/forms", tags=["forms"])


@router.post("/draft-answer", response_model=FormAnswerDraftResponse)
def draft_form_answer_endpoint(payload: FormAnswerDraftCreate) -> FormAnswerDraftResponse:
    trace_id = new_trace_id()

    try:
        master_resume = load_master_resume()
    except MasterResumeNotConfiguredError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    with db_session() as connection:
        try:
            job_lead = get_job_lead(connection, payload.job_lead_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="JobLead not found") from exc

        effective_job = job_lead.model_copy(update={"jd_text": payload.jd_text or job_lead.jd_text})
        ai_config = read_ai_provider_config()
        draft = draft_form_answer(
            effective_job,
            payload.field_context,
            master_resume,
            payload.master_resume_bullets,
            ai_config,
        )

        create_workflow_trace(
            connection,
            WorkflowTraceRecord(
                trace_id=trace_id,
                workflow_name=WORKFLOW_NAME,
                created_at=utc_now(),
                input_summary=f"job_lead_id={payload.job_lead_id}; field={payload.field_context.label[:80]}",
                output_summary="fixed_answer" if not draft.ai_used else "drafted_answer",
                status="completed",
            ),
        )
        prompt_log = create_prompt_log(
            connection,
            PromptLogCreate(
                trace_id=trace_id,
                workflow_name=WORKFLOW_NAME,
                input_summary="fixed answer lookup" if not draft.ai_used else "field context + JD keywords + bullets",
                model="deterministic-form-answer-v1" if not draft.ai_used else (ai_config.model if ai_config else "local_fallback"),
                provider="local_fixed" if not draft.ai_used else (ai_config.provider if ai_config else "local_stub"),
                token_usage=draft.token_usage,
                output_summary="requires_user_review",
            ),
        )
        record = create_form_answer_draft(
            connection,
            FormAnswerDraftRecord(
                id=new_id("fad"),
                job_lead_id=payload.job_lead_id,
                application_id=payload.application_id,
                created_at=utc_now(),
                field_label=payload.field_context.label,
                field_id=payload.field_context.field_id,
                question_text=draft.question_text,
                intent=draft.intent,
                answer_type=draft.answer_type,
                confidence=draft.confidence,
                selected_option=draft.selected_option,
                evidence_summary=draft.evidence_summary or [],
                answer=draft.answer,
                referenced_bullets=draft.referenced_bullets,
                risk_flags=draft.risk_flags,
                requires_user_review=True,
                prompt_log_id=prompt_log.id,
            ),
        )

    return FormAnswerDraftResponse(trace_id=trace_id, draft=record, ai_used=draft.ai_used)


@router.post("/draft-answers", response_model=FormAnswerDraftsResponse)
def draft_form_answers_endpoint(payload: FormAnswerDraftsCreate) -> FormAnswerDraftsResponse:
    trace_id = new_trace_id()

    if not payload.fields:
        raise HTTPException(status_code=422, detail="At least one form field is required.")

    try:
        master_resume = load_master_resume()
    except MasterResumeNotConfiguredError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    with db_session() as connection:
        try:
            job_lead = get_job_lead(connection, payload.job_lead_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="JobLead not found") from exc

        effective_job = job_lead.model_copy(update={"jd_text": payload.jd_text or job_lead.jd_text})
        create_workflow_trace(
            connection,
            WorkflowTraceRecord(
                trace_id=trace_id,
                workflow_name=WORKFLOW_NAME,
                created_at=utc_now(),
                input_summary=f"job_lead_id={payload.job_lead_id}; fields={len(payload.fields)}",
                output_summary=f"drafts={len(payload.fields)}",
                status="completed",
            ),
        )
        ai_config = read_ai_provider_config()
        records: list[FormAnswerDraftRecord] = []
        ai_used = False
        for field_context in payload.fields:
            draft = draft_form_answer(
                effective_job,
                field_context,
                master_resume,
                payload.master_resume_bullets,
                ai_config,
            )
            ai_used = ai_used or draft.ai_used
            prompt_log = create_prompt_log(
                connection,
                PromptLogCreate(
                    trace_id=trace_id,
                    workflow_name=WORKFLOW_NAME,
                    input_summary=(
                        f"batch field={field_context.field_id or field_context.label[:80]}"
                        if not draft.ai_used
                        else "batch field context + JD keywords + bullets"
                    ),
                    model="deterministic-form-answer-v1" if not draft.ai_used else (ai_config.model if ai_config else "local_fallback"),
                    provider="local_fixed" if not draft.ai_used else (ai_config.provider if ai_config else "local_stub"),
                    token_usage=draft.token_usage,
                    output_summary="requires_user_review",
                ),
            )
            records.append(
                create_form_answer_draft(
                    connection,
                    FormAnswerDraftRecord(
                        id=new_id("fad"),
                        job_lead_id=payload.job_lead_id,
                        application_id=payload.application_id,
                        created_at=utc_now(),
                        field_label=field_context.label or field_context.placeholder or field_context.field_id,
                        field_id=field_context.field_id,
                        question_text=draft.question_text,
                        intent=draft.intent,
                        answer_type=draft.answer_type,
                        confidence=draft.confidence,
                        selected_option=draft.selected_option,
                        evidence_summary=draft.evidence_summary or [],
                        answer=draft.answer,
                        referenced_bullets=draft.referenced_bullets,
                        risk_flags=draft.risk_flags,
                        requires_user_review=True,
                        prompt_log_id=prompt_log.id,
                    ),
                )
            )

    return FormAnswerDraftsResponse(
        trace_id=trace_id,
        drafts=records,
        ai_used=ai_used,
        warnings=["Review every answer before filling or submitting the application."],
    )
