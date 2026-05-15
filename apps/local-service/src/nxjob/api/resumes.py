from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException

from nxjob.core.trace import new_trace_id
from nxjob.core.workflow_cache import stable_hash, workflow_cache_key
from nxjob.ai.openai_compatible import AiProviderError
from nxjob.db.connection import db_session
from nxjob.db.repositories import (
    create_prompt_log,
    create_resume_tailor_feedback,
    create_resume_version,
    create_workflow_trace,
    create_workflow_result,
    find_cached_workflow_result,
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
    ResumeTailorFeedbackCreate,
    ResumeTailorFeedbackResponse,
    ResumeTailorResponse,
    ResumeVersionCreate,
    WorkflowCacheInfo,
    WorkflowTraceRecord,
)
from nxjob.settings.private_config import configured_resume_output_dir, read_ai_provider_config, read_ai_provider_status
from nxjob.workflows.resume_tailor import (
    WORKFLOW_NAME,
    extract_keywords,
    tailor_resume_content,
    tailor_resume_content_with_ai,
)

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
    master_resume_bullets = _master_resume_bullets(master_resume) if master_resume else payload.master_resume_bullets
    candidate_name = payload.candidate_name or (master_resume.candidate_name if master_resume else "")
    contact_line = payload.contact_line or (master_resume.contact_line if master_resume else "")
    education = master_resume.education if master_resume else []
    experience = master_resume.experience if master_resume else []

    if not master_resume_bullets:
        raise HTTPException(status_code=422, detail="master_resume_bullets is required")

    try:
        output_dir = _resolve_output_dir(payload.output_directory_override)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

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
        ai_config = read_ai_provider_config()
        (
            _ai_configured,
            _ai_provider_name,
            _ai_model,
            _ai_reasoning_effort,
            _ai_profile_id,
            _ai_profile_display_name,
            ai_provider_source,
        ) = read_ai_provider_status()
        cache_key = workflow_cache_key(
            WORKFLOW_NAME,
            "v3",
            {
                "jd_hash": job_lead.jd_hash,
                "master_resume": stable_hash(
                    {
                        "id": master_resume_id,
                        "candidate_name": candidate_name,
                        "contact_line": contact_line,
                        "bullets": [bullet.model_dump() for bullet in master_resume_bullets],
                        "education": [item.model_dump() for item in education],
                        "experience": [item.model_dump() for item in experience],
                    }
                ),
                "constraints": payload.constraints.model_dump(),
                "output_directory": str(output_dir),
                "filename_policy": "date_company_job_resume",
                "success_references": [reference.id for reference in success_references],
                "ai_provider": {
                    "provider": ai_config.provider if ai_config else "local_stub",
                    "model": ai_config.model if ai_config else "deterministic-tailor-v1",
                },
            },
        )
        if not payload.force_refresh:
            cached = find_cached_workflow_result(connection, WORKFLOW_NAME, cache_key)
            if cached is not None:
                cached_response = ResumeTailorResponse.model_validate(cached.response)
                if _cached_files_exist(cached_response):
                    return cached_response.model_copy(
                        update={"cache": WorkflowCacheInfo(hit=True, cache_key=cache_key)}
                    )

        trace_id = new_trace_id()
        try:
            if ai_config is not None:
                draft = tailor_resume_content_with_ai(
                    job_lead,
                    master_resume_bullets,
                    success_references,
                    ai_config,
                    candidate_name=candidate_name,
                    contact_line=contact_line,
                    education=education,
                    experience=experience,
                )
                ai_used = True
                provider_name = ai_config.provider
                model_name = ai_config.model
            else:
                draft = tailor_resume_content(
                    job_lead,
                    master_resume_bullets,
                    success_references,
                    candidate_name=candidate_name,
                    contact_line=contact_line,
                    education=education,
                    experience=experience,
                )
                ai_used = False
                provider_name = "local_stub"
                model_name = "deterministic-tailor-v1"
        except AiProviderError as exc:
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
                    output_summary=exc.category,
                    status="failed",
                ),
            )
            create_prompt_log(
                connection,
                PromptLogCreate(
                    trace_id=trace_id,
                    workflow_name=WORKFLOW_NAME,
                    input_summary=f"JD keywords only; {len(master_resume_bullets)} master bullets",
                    model=ai_config.model if ai_config is not None else "",
                    provider=ai_config.provider if ai_config is not None else "openai_compatible",
                    token_usage={},
                    output_summary="",
                    error=exc.category,
                ),
            )
            connection.commit()
            raise HTTPException(
                status_code=exc.status_code,
                detail={
                    "message": exc.user_message,
                    "error": {
                        "code": exc.category,
                        "message": exc.user_message,
                        "upstream_status": exc.upstream_status,
                        "retryable": exc.retryable,
                        "provider": ai_config.provider if ai_config is not None else "",
                        "model": ai_config.model if ai_config is not None else "",
                        "config_source": ai_provider_source,
                        "trace_id": trace_id,
                    },
                },
            ) from exc

        filename_base, output_path, markdown_path = _resume_output_paths(job_lead, output_dir)
        render_resume_docx(draft.content, output_path)
        markdown_path.write_text(draft.markdown, encoding="utf-8")
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
                model=model_name,
                provider=provider_name,
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
                ai_output={
                    "content": draft.content.model_dump(),
                    "markdown_path": str(markdown_path),
                    "layout_budget": draft.layout_budget,
                    "quality_checks": draft.quality_checks,
                    "warnings": draft.warnings,
                },
                prompt_log_id=prompt_log.id,
                version_label=trace_id,
                user_approved=False,
            ),
        )
        update_job_lead_status(connection, payload.job_lead_id, "tailored")

    warnings = [*draft.warnings, *validation.warnings]
    if validation.backend == "basic-path-check":
        warnings = [
            *warnings,
            "DOCX layout validation is limited to file existence and budget checks in M11.",
        ]

    response = ResumeTailorResponse(
        trace_id=trace_id,
        resume_version=resume_version,
        used_success_references=[reference.id for reference in success_references],
        warnings=warnings,
        ai_used=ai_used,
        ai_provider_name=provider_name,
        docx_path=str(output_path),
        markdown_path=str(markdown_path),
        filename_base=filename_base,
        layout_budget=draft.layout_budget,
        quality_checks=draft.quality_checks,
        cache=WorkflowCacheInfo(hit=False, cache_key=cache_key),
    )
    with db_session() as connection:
        create_workflow_result(
            connection,
            job_lead_id=payload.job_lead_id,
            workflow_name=WORKFLOW_NAME,
            cache_key=cache_key,
            trace_id=trace_id,
            status="completed",
            result_summary=resume_version.change_summary,
            response=response.model_dump(),
        )

    return response


@router.post("/feedback", response_model=ResumeTailorFeedbackResponse)
def create_tailor_feedback(payload: ResumeTailorFeedbackCreate) -> ResumeTailorFeedbackResponse:
    trace_id = new_trace_id()
    with db_session() as connection:
        try:
            get_job_lead(connection, payload.job_lead_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="JobLead not found") from exc

        feedback = create_resume_tailor_feedback(connection, payload)

    return ResumeTailorFeedbackResponse(trace_id=trace_id, feedback=feedback)


def _resolve_output_dir(override: str = "") -> Path:
    output_dir = Path(override).expanduser() if override.strip() else configured_resume_output_dir()
    if output_dir is None:
        raise ValueError("Resume output folder is not configured.")
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        probe = output_dir / ".nxjob-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        raise ValueError(f"Resume output folder is not writable: {output_dir}") from exc
    return output_dir


def _master_resume_bullets(master_resume) -> list:
    bullets = list(master_resume.bullets)
    for experience in master_resume.experience:
        bullets.extend(experience.bullets)
    return bullets


def _resume_output_paths(job_lead, output_dir: Path) -> tuple[str, Path, Path]:
    date_prefix = job_lead.captured_at[:10] if job_lead.captured_at else utc_now()[:10]
    company = job_lead.company_name or _company_from_title(job_lead.page_title) or "Company"
    title = job_lead.job_title or job_lead.page_title or "Role"
    filename_base = _safe_filename(f"{date_prefix}_{company}_{title}_resume")
    candidate = filename_base
    index = 2
    while (output_dir / f"{candidate}.docx").exists() or (output_dir / f"{candidate}.md").exists():
        candidate = f"{filename_base}_v{index}"
        index += 1
    return candidate, output_dir / f"{candidate}.docx", output_dir / f"{candidate}.md"


def _safe_filename(value: str, max_length: int = 120) -> str:
    normalized = re.sub(r"[\\/:*?\"<>|]+", " ", value)
    normalized = re.sub(r"[^A-Za-z0-9._ -]+", " ", normalized)
    normalized = re.sub(r"\s+", "_", normalized).strip("._- ")
    return (normalized or "tailored_resume")[:max_length].rstrip("._- ")


def _company_from_title(page_title: str) -> str:
    if " at " in page_title:
        return page_title.rsplit(" at ", 1)[-1]
    if " - " in page_title:
        return page_title.rsplit(" - ", 1)[-1]
    return ""


def _cached_files_exist(response: ResumeTailorResponse) -> bool:
    return bool(response.docx_path and response.markdown_path) and Path(response.docx_path).exists() and Path(
        response.markdown_path
    ).exists()
