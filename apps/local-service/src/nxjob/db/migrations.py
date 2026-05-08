from __future__ import annotations

import sqlite3

from nxjob.db.connection import db_session

SCHEMA_VERSION = 6


def initialize_database() -> None:
    with db_session() as connection:
        apply_schema(connection)


def apply_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_meta (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS job_leads (
          id TEXT PRIMARY KEY,
          source_url TEXT NOT NULL,
          source_site TEXT NOT NULL,
          page_title TEXT NOT NULL DEFAULT '',
          company_name TEXT NOT NULL DEFAULT '',
          job_title TEXT NOT NULL DEFAULT '',
          location TEXT NOT NULL DEFAULT '',
          captured_at TEXT NOT NULL,
          jd_text TEXT NOT NULL,
          jd_hash TEXT NOT NULL,
          platform_insights_json TEXT NOT NULL DEFAULT '{}',
          search_query TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL,
          user_notes TEXT NOT NULL DEFAULT ''
        );

        CREATE INDEX IF NOT EXISTS idx_job_leads_jd_hash
          ON job_leads (jd_hash);

        CREATE TABLE IF NOT EXISTS resume_versions (
          id TEXT PRIMARY KEY,
          job_lead_id TEXT NOT NULL,
          source_master_resume_id TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          format TEXT NOT NULL,
          file_path TEXT NOT NULL,
          selected_bullets_json TEXT NOT NULL DEFAULT '[]',
          change_summary TEXT NOT NULL DEFAULT '',
          ai_output_json TEXT NOT NULL DEFAULT '{}',
          prompt_log_id TEXT NOT NULL DEFAULT '',
          version_label TEXT NOT NULL DEFAULT '',
          user_approved INTEGER NOT NULL DEFAULT 0,
          FOREIGN KEY (job_lead_id) REFERENCES job_leads (id)
        );

        CREATE TABLE IF NOT EXISTS applications (
          id TEXT PRIMARY KEY,
          job_lead_id TEXT NOT NULL,
          resume_version_id TEXT,
          applied_at TEXT NOT NULL,
          application_url TEXT NOT NULL DEFAULT '',
          application_method TEXT NOT NULL,
          status TEXT NOT NULL,
          submitted_by_user INTEGER NOT NULL DEFAULT 0,
          follow_up_at TEXT NOT NULL DEFAULT '',
          user_notes TEXT NOT NULL DEFAULT '',
          FOREIGN KEY (job_lead_id) REFERENCES job_leads (id),
          FOREIGN KEY (resume_version_id) REFERENCES resume_versions (id)
        );

        CREATE TABLE IF NOT EXISTS workflow_traces (
          trace_id TEXT PRIMARY KEY,
          workflow_name TEXT NOT NULL,
          created_at TEXT NOT NULL,
          input_summary TEXT NOT NULL DEFAULT '',
          output_summary TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sponsorship_evidence (
          id TEXT PRIMARY KEY,
          job_lead_id TEXT NOT NULL,
          created_at TEXT NOT NULL,
          trace_id TEXT NOT NULL,
          status TEXT NOT NULL,
          confidence REAL NOT NULL,
          source TEXT NOT NULL,
          evidence_text TEXT NOT NULL,
          evidence_url TEXT NOT NULL DEFAULT '',
          is_legal_conclusion INTEGER NOT NULL DEFAULT 0,
          prompt_log_id TEXT NOT NULL DEFAULT '',
          FOREIGN KEY (job_lead_id) REFERENCES job_leads (id),
          FOREIGN KEY (trace_id) REFERENCES workflow_traces (trace_id)
        );

        CREATE INDEX IF NOT EXISTS idx_sponsorship_evidence_job_lead
          ON sponsorship_evidence (job_lead_id, created_at);

        CREATE TABLE IF NOT EXISTS prompt_logs (
          id TEXT PRIMARY KEY,
          trace_id TEXT NOT NULL,
          workflow_name TEXT NOT NULL,
          created_at TEXT NOT NULL,
          input_summary TEXT NOT NULL DEFAULT '',
          model TEXT NOT NULL DEFAULT '',
          provider TEXT NOT NULL DEFAULT '',
          token_usage_json TEXT NOT NULL DEFAULT '{}',
          output_summary TEXT NOT NULL DEFAULT '',
          raw_output_path TEXT NOT NULL DEFAULT '',
          error TEXT NOT NULL DEFAULT '',
          FOREIGN KEY (trace_id) REFERENCES workflow_traces (trace_id)
        );

        CREATE INDEX IF NOT EXISTS idx_prompt_logs_trace_id
          ON prompt_logs (trace_id);

        CREATE TABLE IF NOT EXISTS success_references (
          id TEXT PRIMARY KEY,
          application_id TEXT NOT NULL DEFAULT '',
          job_lead_id TEXT NOT NULL,
          resume_version_id TEXT NOT NULL,
          outcome_type TEXT NOT NULL,
          outcome_at TEXT NOT NULL,
          source TEXT NOT NULL,
          search_query TEXT NOT NULL DEFAULT '',
          effective_keywords_json TEXT NOT NULL DEFAULT '[]',
          effective_bullets_json TEXT NOT NULL DEFAULT '[]',
          user_notes TEXT NOT NULL DEFAULT '',
          FOREIGN KEY (job_lead_id) REFERENCES job_leads (id),
          FOREIGN KEY (resume_version_id) REFERENCES resume_versions (id)
        );

        CREATE INDEX IF NOT EXISTS idx_success_references_job_lead
          ON success_references (job_lead_id, outcome_at);

        CREATE TABLE IF NOT EXISTS form_answer_drafts (
          id TEXT PRIMARY KEY,
          job_lead_id TEXT NOT NULL,
          application_id TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          field_label TEXT NOT NULL DEFAULT '',
          answer TEXT NOT NULL,
          referenced_bullets_json TEXT NOT NULL DEFAULT '[]',
          risk_flags_json TEXT NOT NULL DEFAULT '[]',
          requires_user_review INTEGER NOT NULL DEFAULT 1,
          prompt_log_id TEXT NOT NULL DEFAULT '',
          FOREIGN KEY (job_lead_id) REFERENCES job_leads (id)
        );

        CREATE INDEX IF NOT EXISTS idx_form_answer_drafts_job_lead
          ON form_answer_drafts (job_lead_id, created_at);

        CREATE TABLE IF NOT EXISTS outcome_signals (
          id TEXT PRIMARY KEY,
          application_id TEXT NOT NULL DEFAULT '',
          job_lead_id TEXT NOT NULL,
          created_at TEXT NOT NULL,
          outcome_type TEXT NOT NULL,
          outcome_at TEXT NOT NULL,
          source TEXT NOT NULL,
          evidence_text TEXT NOT NULL DEFAULT '',
          evidence_url TEXT NOT NULL DEFAULT '',
          user_notes TEXT NOT NULL DEFAULT '',
          FOREIGN KEY (job_lead_id) REFERENCES job_leads (id)
        );

        CREATE INDEX IF NOT EXISTS idx_outcome_signals_job_lead
          ON outcome_signals (job_lead_id, outcome_at);

        CREATE INDEX IF NOT EXISTS idx_outcome_signals_application
          ON outcome_signals (application_id, outcome_at);

        CREATE TABLE IF NOT EXISTS workflow_results (
          id TEXT PRIMARY KEY,
          job_lead_id TEXT NOT NULL,
          workflow_name TEXT NOT NULL,
          cache_key TEXT NOT NULL,
          created_at TEXT NOT NULL,
          trace_id TEXT NOT NULL,
          status TEXT NOT NULL,
          result_summary TEXT NOT NULL DEFAULT '',
          response_json TEXT NOT NULL DEFAULT '{}',
          FOREIGN KEY (job_lead_id) REFERENCES job_leads (id),
          FOREIGN KEY (trace_id) REFERENCES workflow_traces (trace_id)
        );

        CREATE INDEX IF NOT EXISTS idx_workflow_results_cache
          ON workflow_results (workflow_name, cache_key, created_at);

        CREATE INDEX IF NOT EXISTS idx_workflow_results_job_lead
          ON workflow_results (job_lead_id, created_at);

        CREATE TABLE IF NOT EXISTS resume_tailor_feedback (
          id TEXT PRIMARY KEY,
          job_lead_id TEXT NOT NULL,
          resume_version_id TEXT NOT NULL,
          created_at TEXT NOT NULL,
          rating TEXT NOT NULL,
          user_notes TEXT NOT NULL DEFAULT '',
          FOREIGN KEY (job_lead_id) REFERENCES job_leads (id),
          FOREIGN KEY (resume_version_id) REFERENCES resume_versions (id)
        );

        CREATE INDEX IF NOT EXISTS idx_resume_tailor_feedback_resume
          ON resume_tailor_feedback (resume_version_id, created_at);
        """
    )
    connection.execute(
        """
        INSERT INTO schema_meta (key, value)
        VALUES ('schema_version', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (str(SCHEMA_VERSION),),
    )
    _ensure_columns(
        connection,
        "sponsorship_evidence",
        {
            "prompt_log_id": "TEXT NOT NULL DEFAULT ''",
        },
    )
    _ensure_columns(
        connection,
        "resume_versions",
        {
            "prompt_log_id": "TEXT NOT NULL DEFAULT ''",
            "version_label": "TEXT NOT NULL DEFAULT ''",
            "user_approved": "INTEGER NOT NULL DEFAULT 0",
        },
    )
    _ensure_columns(
        connection,
        "applications",
        {
            "follow_up_at": "TEXT NOT NULL DEFAULT ''",
            "user_notes": "TEXT NOT NULL DEFAULT ''",
        },
    )
    _ensure_columns(
        connection,
        "job_leads",
        {
            "company_name": "TEXT NOT NULL DEFAULT ''",
            "job_title": "TEXT NOT NULL DEFAULT ''",
            "location": "TEXT NOT NULL DEFAULT ''",
            "user_notes": "TEXT NOT NULL DEFAULT ''",
        },
    )


def _ensure_columns(
    connection: sqlite3.Connection,
    table_name: str,
    columns: dict[str, str],
) -> None:
    existing = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    for column_name, column_definition in columns.items():
        if column_name not in existing:
            connection.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
            )

