from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from nxjob.db.connection import connect
from nxjob.db.migrations import initialize_database
from nxjob.main import create_app
from nxjob.workflows.orchestrator import record_workflow_trace


def test_database_initializes_repeatably(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "nxjob.sqlite3"
    monkeypatch.setenv("NXJOB_DB_PATH", str(db_path))

    initialize_database()
    initialize_database()

    with connect(db_path) as connection:
        version = connection.execute(
            "SELECT value FROM schema_meta WHERE key = 'schema_version'"
        ).fetchone()

    assert version["value"] == "1"


def test_create_and_read_core_records(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))

    with TestClient(create_app()) as client:
        capture_response = client.post(
            "/api/v1/job-leads/capture",
            json={
                "source_url": "https://example.com/jobs/123",
                "source_site": "company_ats",
                "page_title": "Software Engineer",
                "selected_text": "We sponsor qualified candidates for this role.",
                "platform_insights": {"source": "manual"},
                "search_query": "software engineer h1b",
                "user_notes": "Looks relevant.",
            },
        )
        assert capture_response.status_code == 200
        capture_body = capture_response.json()
        assert capture_body["trace_id"].startswith("trc_")
        job_id = capture_body["job_lead"]["id"]

        read_job = client.get(f"/api/v1/job-leads/{job_id}")
        assert read_job.status_code == 200
        assert read_job.json()["jd_text"] == "We sponsor qualified candidates for this role."

        resume_response = client.post(
            "/api/v1/resume-versions",
            json={
                "job_lead_id": job_id,
                "source_master_resume_id": "master_default",
                "file_path": "D:/Codex/NxJob/generated/resume.docx",
                "selected_bullets": ["bullet_1", "bullet_2"],
                "change_summary": "Focused on backend automation.",
                "ai_output": {"summary": "Generated"},
                "version_label": "v1",
                "user_approved": True,
            },
        )
        assert resume_response.status_code == 200
        resume_body = resume_response.json()
        assert resume_body["trace_id"].startswith("trc_")
        resume_id = resume_body["resume_version"]["id"]

        read_resume = client.get(f"/api/v1/resume-versions/{resume_id}")
        assert read_resume.status_code == 200
        assert read_resume.json()["selected_bullets"] == ["bullet_1", "bullet_2"]

        application_response = client.post(
            "/api/v1/applications",
            json={
                "job_lead_id": job_id,
                "resume_version_id": resume_id,
                "application_url": "https://example.com/apply/123",
                "application_method": "external_ats",
                "submitted_by_user": True,
                "user_notes": "Submitted manually.",
            },
        )
        assert application_response.status_code == 200
        application_body = application_response.json()
        assert application_body["trace_id"].startswith("trc_")
        application_id = application_body["application"]["id"]

        read_application = client.get(f"/api/v1/applications/{application_id}")
        assert read_application.status_code == 200
        assert read_application.json()["status"] == "applied"


def test_capture_requires_text(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/v1/job-leads/capture",
            json={
                "source_url": "https://example.com/jobs/empty",
                "source_site": "other",
            },
        )

    assert response.status_code == 422


def test_workflow_trace_is_recorded(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "nxjob.sqlite3"
    monkeypatch.setenv("NXJOB_DB_PATH", str(db_path))
    initialize_database()

    trace = record_workflow_trace(
        "analyze_sponsorship",
        input_summary="JD unclear",
        output_summary="needs_confirmation",
    )

    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT workflow_name, status FROM workflow_traces WHERE trace_id = ?",
            (trace.trace_id,),
        ).fetchone()

    assert trace.trace_id.startswith("trc_")
    assert row == ("analyze_sponsorship", "completed")

