from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from uuid import uuid4

from nxjob.schemas.core import (
    ApplicationCreate,
    ApplicationRecord,
    JobLeadCapture,
    JobLeadRecord,
    ResumeVersionCreate,
    ResumeVersionRecord,
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


def get_resume_version(connection: sqlite3.Connection, record_id: str) -> ResumeVersionRecord:
    row = connection.execute("SELECT * FROM resume_versions WHERE id = ?", (record_id,)).fetchone()
    if row is None:
        raise KeyError(record_id)
    return row_to_resume_version(row)


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

