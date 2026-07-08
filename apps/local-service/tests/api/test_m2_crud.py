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
                "job_title": "Controls Engineer",
                "company_name": "ACME Controls",
                "location": "Boston, MA",
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
        assert read_job.json()["job_title"] == "Controls Engineer"
        assert read_job.json()["company_name"] == "ACME Controls"
        assert read_job.json()["location"] == "Boston, MA"

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


def test_capture_auto_updates_existing_job_when_same_canonical_url_has_no_linked_records(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))

    with TestClient(create_app()) as client:
        first = client.post(
            "/api/v1/job-leads/capture",
            json={
                "source_url": "https://www.linkedin.com/jobs/view/123456789/?currentJobId=123456789",
                "source_site": "linkedin",
                "page_title": "First title",
                "job_title": "Platform Engineer",
                "company_name": "First Company",
                "location": "Boston, MA",
                "selected_text": "Original JD text",
                "capture_metadata": {
                    "canonical_url": "https://www.linkedin.com/jobs/view/123456789/",
                    "raw_url": "https://www.linkedin.com/jobs/view/123456789/?currentJobId=123456789",
                },
            },
        )
        assert first.status_code == 200
        existing_id = first.json()["job_lead"]["id"]

        second = client.post(
            "/api/v1/job-leads/capture",
            json={
                "source_url": "https://www.linkedin.com/jobs/view/123456789/",
                "source_site": "linkedin",
                "page_title": "Updated title",
                "job_title": "Senior Platform Engineer",
                "company_name": "Updated Company",
                "location": "New York, NY",
                "selected_text": "Updated JD text with new details",
                "capture_metadata": {
                    "canonical_url": "https://www.linkedin.com/jobs/view/123456789/",
                    "raw_url": "https://www.linkedin.com/jobs/view/123456789/",
                },
            },
        )

    assert second.status_code == 200
    body = second.json()
    assert body["job_lead"]["id"] == existing_id
    assert body["job_lead"]["job_title"] == "Senior Platform Engineer"
    assert body["job_lead"]["company_name"] == "Updated Company"
    assert body["job_lead"]["jd_text"] == "Updated JD text with new details"
    assert body["dedupe"] == {
        "is_duplicate": True,
        "existing_job_lead_id": existing_id,
        "action": "update_existing",
        "requires_user_choice": False,
        "warnings": [],
    }


def test_capture_requires_user_choice_when_same_canonical_url_has_linked_records(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))

    with TestClient(create_app()) as client:
        capture = client.post(
            "/api/v1/job-leads/capture",
            json={
                "source_url": "https://www.linkedin.com/jobs/view/222222222/",
                "source_site": "linkedin",
                "page_title": "Original title",
                "job_title": "Controls Engineer",
                "company_name": "ACME Controls",
                "location": "Boston, MA",
                "selected_text": "Original JD text",
                "capture_metadata": {
                    "canonical_url": "https://www.linkedin.com/jobs/view/222222222/",
                    "raw_url": "https://www.linkedin.com/jobs/view/222222222/",
                },
            },
        )
        assert capture.status_code == 200
        existing_id = capture.json()["job_lead"]["id"]

        resume = client.post(
            "/api/v1/resume-versions",
            json={
                "job_lead_id": existing_id,
                "source_master_resume_id": "master_default",
                "file_path": "D:/Codex/NxJob/generated/resume.docx",
                "selected_bullets": ["bullet_1"],
                "change_summary": "Focused on controls automation.",
            },
        )
        assert resume.status_code == 200

        second = client.post(
            "/api/v1/job-leads/capture",
            json={
                "source_url": "https://www.linkedin.com/jobs/view/222222222/?trackingId=abc",
                "source_site": "linkedin",
                "page_title": "Updated title",
                "job_title": "Senior Controls Engineer",
                "company_name": "ACME Controls",
                "location": "Chicago, IL",
                "selected_text": "Updated JD text with new details",
                "capture_metadata": {
                    "canonical_url": "https://www.linkedin.com/jobs/view/222222222/",
                    "raw_url": "https://www.linkedin.com/jobs/view/222222222/?trackingId=abc",
                },
            },
        )
        read_existing = client.get(f"/api/v1/job-leads/{existing_id}")

    assert second.status_code == 200
    body = second.json()
    assert body["job_lead"]["id"] == existing_id
    assert body["dedupe"]["is_duplicate"] is True
    assert body["dedupe"]["existing_job_lead_id"] == existing_id
    assert body["dedupe"]["action"] == ""
    assert body["dedupe"]["requires_user_choice"] is True
    assert body["dedupe"]["warnings"]
    assert read_existing.json()["job_title"] == "Controls Engineer"
    assert read_existing.json()["jd_text"] == "Original JD text"


def test_capture_duplicate_action_update_existing_preserves_linked_records(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))

    with TestClient(create_app()) as client:
        capture = client.post(
            "/api/v1/job-leads/capture",
            json={
                "source_url": "https://www.linkedin.com/jobs/view/333333333/",
                "source_site": "linkedin",
                "page_title": "Original title",
                "job_title": "Backend Engineer",
                "company_name": "ACME Controls",
                "location": "Boston, MA",
                "selected_text": "Original JD text",
                "capture_metadata": {
                    "canonical_url": "https://www.linkedin.com/jobs/view/333333333/",
                    "raw_url": "https://www.linkedin.com/jobs/view/333333333/",
                },
            },
        )
        assert capture.status_code == 200
        existing_id = capture.json()["job_lead"]["id"]

        resume = client.post(
            "/api/v1/resume-versions",
            json={
                "job_lead_id": existing_id,
                "source_master_resume_id": "master_default",
                "file_path": "D:/Codex/NxJob/generated/resume.docx",
                "selected_bullets": ["bullet_1"],
                "change_summary": "Focused on backend automation.",
            },
        )
        assert resume.status_code == 200
        resume_id = resume.json()["resume_version"]["id"]

        second = client.post(
            "/api/v1/job-leads/capture",
            json={
                "source_url": "https://www.linkedin.com/jobs/view/333333333/?trackingId=xyz",
                "source_site": "linkedin",
                "page_title": "Updated title",
                "job_title": "Staff Backend Engineer",
                "company_name": "Updated Company",
                "location": "Seattle, WA",
                "selected_text": "Updated JD text with new details",
                "duplicate_action": "update_existing",
                "capture_metadata": {
                    "canonical_url": "https://www.linkedin.com/jobs/view/333333333/",
                    "raw_url": "https://www.linkedin.com/jobs/view/333333333/?trackingId=xyz",
                },
            },
        )
        read_job = client.get(f"/api/v1/job-leads/{existing_id}")
        read_resume = client.get(f"/api/v1/resume-versions/{resume_id}")

    assert second.status_code == 200
    body = second.json()
    assert body["job_lead"]["id"] == existing_id
    assert body["job_lead"]["job_title"] == "Staff Backend Engineer"
    assert body["job_lead"]["company_name"] == "Updated Company"
    assert body["job_lead"]["jd_text"] == "Updated JD text with new details"
    assert body["dedupe"]["action"] == "update_existing"
    assert body["dedupe"]["requires_user_choice"] is False
    assert body["dedupe"]["warnings"] == ["Existing JobLead has linked resume versions."]
    assert read_job.json()["id"] == existing_id
    assert read_resume.json()["job_lead_id"] == existing_id


def test_capture_duplicate_action_create_new_creates_new_record(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))

    with TestClient(create_app()) as client:
        capture = client.post(
            "/api/v1/job-leads/capture",
            json={
                "source_url": "https://www.linkedin.com/jobs/view/444444444/",
                "source_site": "linkedin",
                "page_title": "Original title",
                "job_title": "QA Engineer",
                "company_name": "ACME Controls",
                "location": "Boston, MA",
                "selected_text": "Original JD text",
                "capture_metadata": {
                    "canonical_url": "https://www.linkedin.com/jobs/view/444444444/",
                    "raw_url": "https://www.linkedin.com/jobs/view/444444444/",
                },
            },
        )
        assert capture.status_code == 200
        existing_id = capture.json()["job_lead"]["id"]

        second = client.post(
            "/api/v1/job-leads/capture",
            json={
                "source_url": "https://www.linkedin.com/jobs/view/444444444/?trackingId=retry",
                "source_site": "linkedin",
                "page_title": "Updated title",
                "job_title": "Senior QA Engineer",
                "company_name": "Updated Company",
                "location": "Austin, TX",
                "selected_text": "Updated JD text with new details",
                "duplicate_action": "create_new",
                "capture_metadata": {
                    "canonical_url": "https://www.linkedin.com/jobs/view/444444444/",
                    "raw_url": "https://www.linkedin.com/jobs/view/444444444/?trackingId=retry",
                },
            },
        )

    assert second.status_code == 200
    body = second.json()
    assert body["job_lead"]["id"] != existing_id
    assert body["job_lead"]["job_title"] == "Senior QA Engineer"
    assert body["dedupe"]["is_duplicate"] is True
    assert body["dedupe"]["existing_job_lead_id"] == existing_id
    assert body["dedupe"]["action"] == "create_new"
    assert body["dedupe"]["requires_user_choice"] is False


def test_capture_default_recapture_requires_choice_when_older_same_canonical_url_has_linked_records(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))

    with TestClient(create_app()) as client:
        first = client.post(
            "/api/v1/job-leads/capture",
            json={
                "source_url": "https://www.linkedin.com/jobs/view/555555555/",
                "source_site": "linkedin",
                "page_title": "Original title",
                "job_title": "Systems Engineer",
                "company_name": "ACME Controls",
                "location": "Boston, MA",
                "selected_text": "Original JD text",
                "capture_metadata": {
                    "canonical_url": "https://www.linkedin.com/jobs/view/555555555/",
                    "raw_url": "https://www.linkedin.com/jobs/view/555555555/",
                },
            },
        )
        assert first.status_code == 200
        original_id = first.json()["job_lead"]["id"]

        resume = client.post(
            "/api/v1/resume-versions",
            json={
                "job_lead_id": original_id,
                "source_master_resume_id": "master_default",
                "file_path": "D:/Codex/NxJob/generated/resume.docx",
                "selected_bullets": ["bullet_1"],
                "change_summary": "Focused on systems automation.",
            },
        )
        assert resume.status_code == 200

        create_new = client.post(
            "/api/v1/job-leads/capture",
            json={
                "source_url": "https://www.linkedin.com/jobs/view/555555555/?trackingId=create-new",
                "source_site": "linkedin",
                "page_title": "Retried title",
                "job_title": "Senior Systems Engineer",
                "company_name": "Updated Company",
                "location": "Seattle, WA",
                "selected_text": "Retried JD text",
                "duplicate_action": "create_new",
                "capture_metadata": {
                    "canonical_url": "https://www.linkedin.com/jobs/view/555555555/",
                    "raw_url": "https://www.linkedin.com/jobs/view/555555555/?trackingId=create-new",
                },
            },
        )
        assert create_new.status_code == 200
        newer_id = create_new.json()["job_lead"]["id"]
        assert newer_id != original_id

        recapture = client.post(
            "/api/v1/job-leads/capture",
            json={
                "source_url": "https://www.linkedin.com/jobs/view/555555555/?trackingId=default-recapture",
                "source_site": "linkedin",
                "page_title": "Default recapture title",
                "job_title": "Principal Systems Engineer",
                "company_name": "Third Company",
                "location": "Austin, TX",
                "selected_text": "Default recapture JD text",
                "capture_metadata": {
                    "canonical_url": "https://www.linkedin.com/jobs/view/555555555/",
                    "raw_url": "https://www.linkedin.com/jobs/view/555555555/?trackingId=default-recapture",
                },
            },
        )
        latest_newer = client.get(f"/api/v1/job-leads/{newer_id}")
        latest_original = client.get(f"/api/v1/job-leads/{original_id}")

    assert recapture.status_code == 200
    body = recapture.json()
    assert body["job_lead"]["id"] == newer_id
    assert body["dedupe"]["is_duplicate"] is True
    assert body["dedupe"]["existing_job_lead_id"] == newer_id
    assert body["dedupe"]["action"] == ""
    assert body["dedupe"]["requires_user_choice"] is True
    assert body["dedupe"]["warnings"] == ["Existing JobLead has linked resume versions."]
    assert latest_newer.json()["job_title"] == "Senior Systems Engineer"
    assert latest_newer.json()["jd_text"] == "Retried JD text"
    assert latest_original.json()["job_title"] == "Systems Engineer"

    db_path = tmp_path / "nxjob.sqlite3"
    with connect(db_path) as connection:
        total_rows = connection.execute("SELECT COUNT(*) AS count FROM job_leads").fetchone()

    assert total_rows["count"] == 2


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

