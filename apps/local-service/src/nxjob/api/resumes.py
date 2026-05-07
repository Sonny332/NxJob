from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException

from nxjob.core.trace import new_trace_id
from nxjob.db.connection import db_session
from nxjob.db.repositories import (
    create_prompt_log,
    create_resume_version,
    create_workflow_trace,
    get_job_lead,
    list_success_references,
    update_job_lead_status,
    utc_now,
)
from nxjob.resumes.document_validation import validate_docx_basic
from nxjob.resumes.docx_renderer import render_resume_docx
from nxjob.resumes.master_resume import MasterResumeNotConfiguredError, load_master_resume
from nxjob.schemas.core import (
    PromptLogCreate,
    ResumeTailorRequest,
    ResumeTailorResponse,
    ResumeVersionCreate,
    WorkflowTraceRecord,
)
from nxjob.storage.paths import generated_resume_dir
from nxjob.workflows.resume_tailor import WORKFLOW_NAME, extract_keywords, tailor_resume_content

router = APIRouter(prefix="/api/v1/resumes", tags=["resumes"])


@router.post("/tailor", response_model=ResumeTailorResponse)
def tailor_resume_endpoint(payload: ResumeTailorRequest) -> ResumeTailorResponse:
    if payload.constraints.format != "docx":
        raise HTTPException(status_code=422, detail="MVP only supports DOCX output")

    try:
        master_resume = load_master_resume() if not payload.master_resume_bullets else None
    except MasterResumeNotConfiguredError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    master_resume_id = master_resume.id if master_resume else payload.master_resume_id
    master_resume_bullets = master_resume.bullets if master_resume else payload.master_resume_bullets
    candidate_name = payload.candidate_name or (master_resume.candidate_name if master_resume else "")
    contact_line = payload.contact_line or (master_resume.contact_line if master_resume else "")

    if not master_resume_bullets:
        raise HTTPException(status_code=422, detail="master_resume_bullets is required")

    trace_id = new_trace_id()

    with db_session() as connection:
        try:
            job_lead = get_job_lead(connection, payload.job_lead_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="JobLead not found") from exc

        success_references = list_success_references(
            connection,
            extract_keywords(job_lead.jd_text),
            payload.success_reference_limit,
        )
        draft = tailor_resume_content(
            job_lead,
            master_resume_bullets,
            success_references,
            candidate_name=candidate_name,
            contact_line=contact_line,
        )
        output_path = _resume_output_path(payload.job_lead_id, trace_id)
        render_resume_docx(draft.content, output_path)
        validation = validate_docx_basic(output_path)

        create_workflow_trace(
            connection,
            WorkflowTraceRecord(
                trace_id=trace_id,
                workflow_name=WORKFLOW_NAME,
                created_at=utc_now(),
                input_summary=(
                    f"job_lead_id={payload.job_lead_id}; "
                    f"bullets={len(master_resume_bullets)}; "
                    f"success_reference_limit={payload.success_reference_limit}"
                ),
                output_summary=draft.change_summary,
                status="completed",
            ),
        )
        prompt_log = create_prompt_log(
            connection,
            PromptLogCreate(
                trace_id=trace_id,
                workflow_name=WORKFLOW_NAME,
                input_summary=f"JD keywords only; {len(master_resume_bullets)} master bullets",
                model="deterministic-tailor-v1",
                provider="local_stub",
                token_usage=draft.token_usage,
                output_summary=draft.change_summary,
            ),
        )
        resume_version = create_resume_version(
            connection,
            ResumeVersionCreate(
                job_lead_id=payload.job_lead_id,
                source_master_resume_id=master_resume_id,
                format="docx",
                file_path=str(output_path),
                selected_bullets=draft.selected_bullet_ids,
                change_summary=draft.change_summary,
                ai_output=draft.content.model_dump(),
                prompt_log_id=prompt_log.id,
                version_label=trace_id,
                user_approved=False,
            ),
        )
        update_job_lead_status(connection, payload.job_lead_id, "tailored")

    warnings = validation.warnings
    if validation.backend == "basic-path-check":
        warnings = [
            *warnings,
            "DOCX layout validation is limited to file existence in M5.",
        ]

    return ResumeTailorResponse(
        trace_id=trace_id,
        resume_version=resume_version,
        used_success_references=[reference.id for reference in success_references],
        warnings=warnings,
    )


def _resume_output_path(job_lead_id: str, trace_id: str) -> Path:
    safe_job_id = re.sub(r"[^A-Za-z0-9_-]+", "_", job_lead_id)
    return generated_resume_dir() / f"{safe_job_id}_{trace_id}.docx"
