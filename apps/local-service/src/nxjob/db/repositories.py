from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from uuid import uuid4

from nxjob.schemas.core import (
    ApplicationCreate,
    ApplicationRecord,
    FormAnswerDraftRecord,
    JobLeadCapture,
    JobLeadRecord,
    OutcomeSignalCreate,
    OutcomeSignalRecord,
    PromptLogCreate,
    PromptLogRecord,
    ResumeTailorFeedbackCreate,
    ResumeTailorFeedbackRecord,
    ResumeVersionCreate,
    ResumeVersionRecord,
    SponsorshipAnalyzeResponse,
    SuccessReferenceCreate,
    SuccessReferenceRecord,
    WorkflowResultRecord,
    WorkflowTraceRecord,
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def jd_hash(text: str) -> str:
    normalized = " ".join(text.lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def row_to_job_lead(row: sqlite3.Row) -> JobLeadRecord:
    return JobLeadRecord(
        id=row["id"],
        source_url=row["source_url"],
        source_site=row["source_site"],
        page_title=row["page_title"],
        company_name=row["company_name"],
        job_title=row["job_title"],
        location=row["location"],
        captured_at=row["captured_at"],
        jd_text=row["jd_text"],
        jd_hash=row["jd_hash"],
        platform_insights=json.loads(row["platform_insights_json"] or "{}"),
        search_query=row["search_query"],
        status=row["status"],
        user_notes=row["user_notes"],
    )


def create_job_lead(connection: sqlite3.Connection, payload: JobLeadCapture) -> tuple[JobLeadRecord, str | None]:
    text = payload.selected_text or payload.page_text_excerpt
    digest = jd_hash(text)
    duplicate = connection.execute(
        "SELECT id FROM job_leads WHERE jd_hash = ? ORDER BY captured_at DESC LIMIT 1",
        (digest,),
    ).fetchone()

    record_id = new_id("job")
    connection.execute(
        """
        INSERT INTO job_leads (
          id, source_url, source_site, page_title, captured_at, jd_text, jd_hash,
          platform_insights_json, search_query, status, user_notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'captured', ?)
        """,
        (
            record_id,
            str(payload.source_url),
            payload.source_site,
            payload.page_title,
            utc_now(),
            text,
            digest,
            json.dumps(payload.platform_insights, ensure_ascii=False),
            payload.search_query,
            payload.user_notes,
        ),
    )
    return get_job_lead(connection, record_id), duplicate["id"] if duplicate else None


def get_job_lead(connection: sqlite3.Connection, record_id: str) -> JobLeadRecord:
    row = connection.execute("SELECT * FROM job_leads WHERE id = ?", (record_id,)).fetchone()
    if row is None:
        raise KeyError(record_id)
    return row_to_job_lead(row)


def row_to_resume_version(row: sqlite3.Row) -> ResumeVersionRecord:
    return ResumeVersionRecord(
        id=row["id"],
        job_lead_id=row["job_lead_id"],
        source_master_resume_id=row["source_master_resume_id"],
        created_at=row["created_at"],
        format=row["format"],
        file_path=row["file_path"],
        selected_bullets=json.loads(row["selected_bullets_json"] or "[]"),
        change_summary=row["change_summary"],
        ai_output=json.loads(row["ai_output_json"] or "{}"),
        prompt_log_id=row["prompt_log_id"],
        version_label=row["version_label"],
        user_approved=bool(row["user_approved"]),
    )


def create_resume_version(
    connection: sqlite3.Connection,
    payload: ResumeVersionCreate,
) -> ResumeVersionRecord:
    record_id = new_id("res")
    connection.execute(
        """
        INSERT INTO resume_versions (
          id, job_lead_id, source_master_resume_id, created_at, format, file_path,
          selected_bullets_json, change_summary, ai_output_json, prompt_log_id,
          version_label, user_approved
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record_id,
            payload.job_lead_id,
            payload.source_master_resume_id,
            utc_now(),
            payload.format,
            payload.file_path,
            json.dumps(payload.selected_bullets, ensure_ascii=False),
            payload.change_summary,
            json.dumps(payload.ai_output, ensure_ascii=False),
            payload.prompt_log_id,
            payload.version_label,
            int(payload.user_approved),
        ),
    )
    return get_resume_version(connection, record_id)


def get_resume_version_for_job_by_file_path(
    connection: sqlite3.Connection,
    job_lead_id: str,
    file_path: str,
) -> ResumeVersionRecord | None:
    row = connection.execute(
        """
        SELECT * FROM resume_versions
        WHERE job_lead_id = ? AND file_path = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (job_lead_id, file_path),
    ).fetchone()
    return row_to_resume_version(row) if row else None


def get_resume_version(connection: sqlite3.Connection, record_id: str) -> ResumeVersionRecord:
    row = connection.execute("SELECT * FROM resume_versions WHERE id = ?", (record_id,)).fetchone()
    if row is None:
        raise KeyError(record_id)
    return row_to_resume_version(row)


def get_latest_resume_version_for_job(
    connection: sqlite3.Connection,
    job_lead_id: str,
) -> ResumeVersionRecord | None:
    row = connection.execute(
        """
        SELECT * FROM resume_versions
        WHERE job_lead_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (job_lead_id,),
    ).fetchone()
    return row_to_resume_version(row) if row else None


def update_job_lead_status(connection: sqlite3.Connection, record_id: str, status: str) -> None:
    connection.execute(
        "UPDATE job_leads SET status = ? WHERE id = ?",
        (status, record_id),
    )


def update_application_status(connection: sqlite3.Connection, record_id: str, status: str) -> None:
    connection.execute(
        "UPDATE applications SET status = ? WHERE id = ?",
        (status, record_id),
    )


def row_to_application(row: sqlite3.Row) -> ApplicationRecord:
    return ApplicationRecord(
        id=row["id"],
        job_lead_id=row["job_lead_id"],
        resume_version_id=row["resume_version_id"],
        applied_at=row["applied_at"],
        application_url=row["application_url"],
        application_method=row["application_method"],
        status=row["status"],
        submitted_by_user=bool(row["submitted_by_user"]),
        follow_up_at=row["follow_up_at"],
        user_notes=row["user_notes"],
    )


def create_application(
    connection: sqlite3.Connection,
    payload: ApplicationCreate,
) -> ApplicationRecord:
    record_id = new_id("app")
    status = "applied" if payload.submitted_by_user else "ready_to_apply"
    connection.execute(
        """
        INSERT INTO applications (
          id, job_lead_id, resume_version_id, applied_at, application_url,
          application_method, status, submitted_by_user, follow_up_at, user_notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record_id,
            payload.job_lead_id,
            payload.resume_version_id,
            payload.applied_at or utc_now(),
            str(payload.application_url),
            payload.application_method,
            status,
            int(payload.submitted_by_user),
            payload.follow_up_at,
            payload.user_notes,
        ),
    )
    return get_application(connection, record_id)


def get_application(connection: sqlite3.Connection, record_id: str) -> ApplicationRecord:
    row = connection.execute("SELECT * FROM applications WHERE id = ?", (record_id,)).fetchone()
    if row is None:
        raise KeyError(record_id)
    return row_to_application(row)


def create_workflow_trace(
    connection: sqlite3.Connection,
    record: WorkflowTraceRecord,
) -> WorkflowTraceRecord:
    connection.execute(
        """
        INSERT INTO workflow_traces (
          trace_id, workflow_name, created_at, input_summary, output_summary, status
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            record.trace_id,
            record.workflow_name,
            record.created_at,
            record.input_summary,
            record.output_summary,
            record.status,
        ),
    )
    return record


def row_to_prompt_log(row: sqlite3.Row) -> PromptLogRecord:
    return PromptLogRecord(
        id=row["id"],
        trace_id=row["trace_id"],
        workflow_name=row["workflow_name"],
        created_at=row["created_at"],
        input_summary=row["input_summary"],
        model=row["model"],
        provider=row["provider"],
        token_usage=json.loads(row["token_usage_json"] or "{}"),
        output_summary=row["output_summary"],
        raw_output_path=row["raw_output_path"],
        error=row["error"],
    )


def create_prompt_log(connection: sqlite3.Connection, payload: PromptLogCreate) -> PromptLogRecord:
    record_id = new_id("prm")
    connection.execute(
        """
        INSERT INTO prompt_logs (
          id, trace_id, workflow_name, created_at, input_summary, model, provider,
          token_usage_json, output_summary, raw_output_path, error
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record_id,
            payload.trace_id,
            payload.workflow_name,
            utc_now(),
            payload.input_summary,
            payload.model,
            payload.provider,
            json.dumps(payload.token_usage, ensure_ascii=False),
            payload.output_summary,
            payload.raw_output_path,
            payload.error,
        ),
    )
    return get_prompt_log(connection, record_id)


def row_to_workflow_result(row: sqlite3.Row) -> WorkflowResultRecord:
    return WorkflowResultRecord(
        id=row["id"],
        job_lead_id=row["job_lead_id"],
        workflow_name=row["workflow_name"],
        cache_key=row["cache_key"],
        created_at=row["created_at"],
        trace_id=row["trace_id"],
        status=row["status"],
        result_summary=row["result_summary"],
        response=json.loads(row["response_json"] or "{}"),
    )


def create_workflow_result(
    connection: sqlite3.Connection,
    *,
    job_lead_id: str,
    workflow_name: str,
    cache_key: str,
    trace_id: str,
    status: str,
    result_summary: str,
    response: dict[str, object],
) -> WorkflowResultRecord:
    record_id = new_id("wfr")
    connection.execute(
        """
        INSERT INTO workflow_results (
          id, job_lead_id, workflow_name, cache_key, created_at, trace_id,
          status, result_summary, response_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record_id,
            job_lead_id,
            workflow_name,
            cache_key,
            utc_now(),
            trace_id,
            status,
            result_summary,
            json.dumps(response, ensure_ascii=False),
        ),
    )
    row = connection.execute("SELECT * FROM workflow_results WHERE id = ?", (record_id,)).fetchone()
    return row_to_workflow_result(row)


def find_cached_workflow_result(
    connection: sqlite3.Connection,
    workflow_name: str,
    cache_key: str,
) -> WorkflowResultRecord | None:
    row = connection.execute(
        """
        SELECT * FROM workflow_results
        WHERE workflow_name = ? AND cache_key = ? AND status = 'completed'
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (workflow_name, cache_key),
    ).fetchone()
    return row_to_workflow_result(row) if row else None


def list_workflow_results_for_job(
    connection: sqlite3.Connection,
    job_lead_id: str,
    limit: int = 20,
) -> list[WorkflowResultRecord]:
    rows = connection.execute(
        """
        SELECT * FROM workflow_results
        WHERE job_lead_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (job_lead_id, limit),
    ).fetchall()
    return [row_to_workflow_result(row) for row in rows]


def get_prompt_log(connection: sqlite3.Connection, record_id: str) -> PromptLogRecord:
    row = connection.execute("SELECT * FROM prompt_logs WHERE id = ?", (record_id,)).fetchone()
    if row is None:
        raise KeyError(record_id)
    return row_to_prompt_log(row)


def row_to_success_reference(row: sqlite3.Row) -> SuccessReferenceRecord:
    return SuccessReferenceRecord(
        id=row["id"],
        application_id=row["application_id"],
        job_lead_id=row["job_lead_id"],
        resume_version_id=row["resume_version_id"],
        outcome_type=row["outcome_type"],
        outcome_at=row["outcome_at"],
        source=row["source"],
        search_query=row["search_query"],
        effective_keywords=json.loads(row["effective_keywords_json"] or "[]"),
        effective_bullets=json.loads(row["effective_bullets_json"] or "[]"),
        user_notes=row["user_notes"],
    )


def create_success_reference(
    connection: sqlite3.Connection,
    payload: SuccessReferenceCreate,
) -> SuccessReferenceRecord:
    record_id = new_id("sref")
    connection.execute(
        """
        INSERT INTO success_references (
          id, application_id, job_lead_id, resume_version_id, outcome_type, outcome_at,
          source, search_query, effective_keywords_json, effective_bullets_json, user_notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record_id,
            payload.application_id,
            payload.job_lead_id,
            payload.resume_version_id,
            payload.outcome_type,
            payload.outcome_at,
            payload.source,
            payload.search_query,
            json.dumps(payload.effective_keywords, ensure_ascii=False),
            json.dumps(payload.effective_bullets, ensure_ascii=False),
            payload.user_notes,
        ),
    )
    return get_success_reference(connection, record_id)


def get_success_reference(connection: sqlite3.Connection, record_id: str) -> SuccessReferenceRecord:
    row = connection.execute("SELECT * FROM success_references WHERE id = ?", (record_id,)).fetchone()
    if row is None:
        raise KeyError(record_id)
    return row_to_success_reference(row)


def list_success_references_for_tracker(
    connection: sqlite3.Connection,
    limit: int = 50,
) -> list[SuccessReferenceRecord]:
    rows = connection.execute(
        "SELECT * FROM success_references ORDER BY outcome_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [row_to_success_reference(row) for row in rows]


def list_success_references(
    connection: sqlite3.Connection,
    keywords: list[str],
    limit: int,
) -> list[SuccessReferenceRecord]:
    if limit <= 0:
        return []

    rows = connection.execute(
        "SELECT * FROM success_references ORDER BY outcome_at DESC LIMIT 50"
    ).fetchall()
    references = [row_to_success_reference(row) for row in rows]
    keyword_set = {keyword.lower() for keyword in keywords}

    def score(reference: SuccessReferenceRecord) -> tuple[int, str]:
        matched = keyword_set.intersection(keyword.lower() for keyword in reference.effective_keywords)
        return len(matched), reference.outcome_at

    return sorted(references, key=score, reverse=True)[:limit]


def create_form_answer_draft(
    connection: sqlite3.Connection,
    payload: FormAnswerDraftRecord,
) -> FormAnswerDraftRecord:
    connection.execute(
        """
        INSERT INTO form_answer_drafts (
          id, job_lead_id, application_id, created_at, field_label, answer,
          referenced_bullets_json, risk_flags_json, requires_user_review, prompt_log_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload.id,
            payload.job_lead_id,
            payload.application_id,
            payload.created_at,
            payload.field_label,
            payload.answer,
            json.dumps(payload.referenced_bullets, ensure_ascii=False),
            json.dumps(payload.risk_flags, ensure_ascii=False),
            int(payload.requires_user_review),
            payload.prompt_log_id,
        ),
    )
    return payload


def row_to_outcome_signal(row: sqlite3.Row) -> OutcomeSignalRecord:
    return OutcomeSignalRecord(
        id=row["id"],
        application_id=row["application_id"],
        job_lead_id=row["job_lead_id"],
        created_at=row["created_at"],
        outcome_type=row["outcome_type"],
        outcome_at=row["outcome_at"],
        source=row["source"],
        evidence_text=row["evidence_text"],
        evidence_url=row["evidence_url"],
        user_notes=row["user_notes"],
    )


def create_outcome_signal(
    connection: sqlite3.Connection,
    payload: OutcomeSignalCreate,
) -> OutcomeSignalRecord:
    record_id = new_id("out")
    outcome_at = payload.outcome_at or utc_now()
    connection.execute(
        """
        INSERT INTO outcome_signals (
          id, application_id, job_lead_id, created_at, outcome_type, outcome_at,
          source, evidence_text, evidence_url, user_notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record_id,
            payload.application_id,
            payload.job_lead_id,
            utc_now(),
            payload.outcome_type,
            outcome_at,
            payload.source,
            payload.evidence_text,
            payload.evidence_url,
            payload.user_notes,
        ),
    )
    return get_outcome_signal(connection, record_id)


def get_outcome_signal(connection: sqlite3.Connection, record_id: str) -> OutcomeSignalRecord:
    row = connection.execute("SELECT * FROM outcome_signals WHERE id = ?", (record_id,)).fetchone()
    if row is None:
        raise KeyError(record_id)
    return row_to_outcome_signal(row)


def create_sponsorship_evidence(
    connection: sqlite3.Connection,
    job_lead_id: str,
    trace_id: str,
    analysis: SponsorshipAnalyzeResponse,
) -> None:
    for item in analysis.evidence:
        connection.execute(
            """
            INSERT INTO sponsorship_evidence (
              id, job_lead_id, created_at, trace_id, status, confidence, source,
              evidence_text, evidence_url, is_legal_conclusion, prompt_log_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '')
            """,
            (
                new_id("spn"),
                job_lead_id,
                utc_now(),
                trace_id,
                analysis.sponsorship.status,
                item.confidence,
                item.source,
                item.evidence_text,
                item.evidence_url,
                int(analysis.sponsorship.is_legal_conclusion),
            ),
        )


def create_resume_tailor_feedback(
    connection: sqlite3.Connection,
    payload: ResumeTailorFeedbackCreate,
) -> ResumeTailorFeedbackRecord:
    record = ResumeTailorFeedbackRecord(
        id=new_id("rfb"),
        job_lead_id=payload.job_lead_id,
        resume_version_id=payload.resume_version_id,
        created_at=utc_now(),
        rating=payload.rating,
        user_notes=payload.user_notes,
    )
    connection.execute(
        """
        INSERT INTO resume_tailor_feedback (
          id, job_lead_id, resume_version_id, created_at, rating, user_notes
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            record.id,
            record.job_lead_id,
            record.resume_version_id,
            record.created_at,
            record.rating,
            record.user_notes,
        ),
    )
    return record

