from __future__ import annotations

import sqlite3

from nxjob.db.connection import db_session

SCHEMA_VERSION = 1


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

