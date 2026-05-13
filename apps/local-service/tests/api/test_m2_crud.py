from __future__ import annotations

import sqlite3
from pathlib import Path

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

    assert version["value"] == "6"


def test_database_migrates_legacy_sponsorship_evidence_schema(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "nxjob.sqlite3"
    monkeypatch.setenv("NXJOB_DB_PATH", str(db_path))

    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE schema_meta (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL
            );
            INSERT INTO schema_meta (key, value) VALUES ('schema_version', '5');

            CREATE TABLE sponsorship_evidence (
              id TEXT PRIMARY KEY,
              job_lead_id TEXT NOT NULL,
              created_at TEXT NOT NULL,
              trace_id TEXT NOT NULL,
              status TEXT NOT NULL,
              confidence REAL NOT NULL,
              source TEXT NOT NULL,
              evidence_text TEXT NOT NULL,
              evidence_url TEXT NOT NULL DEFAULT '',
              is_legal_conclusion INTEGER NOT NULL DEFAULT 0
            );
            """
        )

    initialize_database()

    with connect(db_path) as connection:
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(sponsorship_evidence)")
        }
        version = connection.execute(
            "SELECT value FROM schema_meta WHERE key = 'schema_version'"
        ).fetchone()

    assert "prompt_log_id" in columns
    assert version["value"] == "6"


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


def test_resume_version_artifacts_return_registered_docx_and_markdown(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))
    monkeypatch.setenv("NXJOB_GENERATED_RESUME_DIR", str(tmp_path / "generated"))
    docx_path = tmp_path / "generated" / "resume.docx"
    markdown_path = tmp_path / "generated" / "resume.md"
    docx_path.parent.mkdir()
    docx_path.write_bytes(b"docx-bytes")
    markdown_path.write_text("# Resume\n", encoding="utf-8")

    with TestClient(create_app()) as client:
        job_id = _capture_job(client)
        resume_id = _create_resume_version(
            client,
            job_id,
            file_path=docx_path,
            ai_output={"markdown_path": str(markdown_path)},
        )

        docx = client.get(f"/api/v1/resume-versions/{resume_id}/artifacts/docx")
        markdown = client.get(f"/api/v1/resume-versions/{resume_id}/artifacts/markdown")

    assert docx.status_code == 200
    assert docx.content == b"docx-bytes"
    assert "resume.docx" in docx.headers["content-disposition"]
    assert markdown.status_code == 200
    assert markdown.text.splitlines() == ["# Resume"]


def test_resume_version_artifact_missing_file_returns_readable_error(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))
    monkeypatch.setenv("NXJOB_GENERATED_RESUME_DIR", str(tmp_path / "generated"))

    with TestClient(create_app()) as client:
        job_id = _capture_job(client)
        resume_id = _create_resume_version(
            client,
            job_id,
            file_path=tmp_path / "generated" / "missing.docx",
            ai_output={"markdown_path": str(tmp_path / "generated" / "missing.md")},
        )

        response = client.get(f"/api/v1/resume-versions/{resume_id}/artifacts/docx")

    assert response.status_code == 404
    assert response.json()["detail"] == "Resume artifact file is missing."


def test_resume_version_artifact_rejects_unregistered_or_wrong_type_path(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))
    monkeypatch.setenv("NXJOB_GENERATED_RESUME_DIR", str(tmp_path / "generated"))
    secret_path = tmp_path / "private.txt"
    secret_path.write_text("do not read", encoding="utf-8")

    with TestClient(create_app()) as client:
        job_id = _capture_job(client)
        resume_id = _create_resume_version(client, job_id, file_path=secret_path)

        response = client.get(f"/api/v1/resume-versions/{resume_id}/artifacts/docx")

    assert response.status_code == 422
    assert response.json()["detail"] == "Registered DOCX artifact path is invalid."
    assert "do not read" not in response.text


def test_resume_version_artifact_rejects_docx_outside_output_folder(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))
    monkeypatch.setenv("NXJOB_GENERATED_RESUME_DIR", str(tmp_path / "generated"))
    outside_docx = tmp_path / "private" / "secret.docx"
    outside_docx.parent.mkdir()
    outside_docx.write_bytes(b"private docx bytes")

    with TestClient(create_app()) as client:
        job_id = _capture_job(client)
        resume_id = _create_resume_version(client, job_id, file_path=outside_docx)

        response = client.get(f"/api/v1/resume-versions/{resume_id}/artifacts/docx")

    assert response.status_code == 422
    assert response.json()["detail"] == "Registered resume artifact path is outside configured output folder."
    assert b"private docx bytes" not in response.content


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


def _capture_job(client: TestClient) -> str:
    response = client.post(
        "/api/v1/job-leads/capture",
        json={
            "source_url": "https://example.com/jobs/artifact",
            "source_site": "company_ats",
            "page_title": "Artifact test",
            "selected_text": "Python API role.",
        },
    )
    assert response.status_code == 200
    return response.json()["job_lead"]["id"]


def _create_resume_version(
    client: TestClient,
    job_id: str,
    *,
    file_path: Path,
    ai_output: dict[str, str] | None = None,
) -> str:
    response = client.post(
        "/api/v1/resume-versions",
        json={
            "job_lead_id": job_id,
            "source_master_resume_id": "master_default",
            "file_path": str(file_path),
            "selected_bullets": ["bullet_1"],
            "change_summary": "Focused on API work.",
            "ai_output": ai_output or {},
        },
    )
    assert response.status_code == 200
    return response.json()["resume_version"]["id"]

