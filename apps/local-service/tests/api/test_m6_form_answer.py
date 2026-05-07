from __future__ import annotations

import json
import sqlite3

from fastapi.testclient import TestClient

from nxjob.main import create_app


def test_draft_answer_uses_fixed_profile_answer_without_ai(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "nxjob.sqlite3"
    master_path = _write_master_resume(tmp_path)
    monkeypatch.setenv("NXJOB_DB_PATH", str(db_path))
    monkeypatch.setenv("NXJOB_MASTER_RESUME_PATH", str(master_path))

    with TestClient(create_app()) as client:
        job_id = _capture_job(client)
        response = client.post(
            "/api/v1/forms/draft-answer",
            json={
                "job_lead_id": job_id,
                "field_context": {
                    "label": "Email",
                    "placeholder": "email@example.com",
                    "surrounding_text": "Contact information",
                    "current_value": "",
                    "input_type": "email",
                },
            },
        )

    body = response.json()
    assert response.status_code == 200
    assert body["ai_used"] is False
    assert body["draft"]["answer"] == "candidate@example.com"
    assert body["draft"]["requires_user_review"] is True

    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT answer FROM form_answer_drafts WHERE job_lead_id = ?",
            (job_id,),
        ).fetchone()

    assert row[0] == "candidate@example.com"


def test_draft_answer_uses_resume_bullets_for_open_question(tmp_path, monkeypatch) -> None:
    master_path = _write_master_resume(tmp_path)
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))
    monkeypatch.setenv("NXJOB_MASTER_RESUME_PATH", str(master_path))

    with TestClient(create_app()) as client:
        job_id = _capture_job(client)
        response = client.post(
            "/api/v1/forms/draft-answer",
            json={
                "job_lead_id": job_id,
                "field_context": {
                    "label": "Why are you interested in this role?",
                    "surrounding_text": "Tell us why this automation platform role is a fit.",
                },
            },
        )

    body = response.json()
    assert response.status_code == 200
    assert body["ai_used"] is True
    assert "FastAPI" in body["draft"]["answer"]
    assert body["draft"]["referenced_bullets"] == ["bullet_api"]
    assert body["draft"]["risk_flags"]


def test_tailor_resume_can_load_private_master_resume(tmp_path, monkeypatch) -> None:
    master_path = _write_master_resume(tmp_path)
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))
    monkeypatch.setenv("NXJOB_MASTER_RESUME_PATH", str(master_path))
    monkeypatch.setenv("NXJOB_GENERATED_RESUME_DIR", str(tmp_path / "generated"))

    with TestClient(create_app()) as client:
        job_id = _capture_job(client)
        response = client.post(
            "/api/v1/resumes/tailor",
            json={"job_lead_id": job_id},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["resume_version"]["source_master_resume_id"] == "master_test"
    assert body["resume_version"]["selected_bullets"] == ["bullet_api"]


def _capture_job(client: TestClient) -> str:
    response = client.post(
        "/api/v1/job-leads/capture",
        json={
            "source_url": "https://example.com/jobs/form-answer",
            "source_site": "company_ats",
            "page_title": "Automation Platform Engineer",
            "selected_text": "Automation platform role using Python, FastAPI, and workflow APIs.",
        },
    )
    assert response.status_code == 200
    return response.json()["job_lead"]["id"]


def _write_master_resume(tmp_path) -> str:
    path = tmp_path / "master_resume.json"
    path.write_text(
        json.dumps(
            {
                "id": "master_test",
                "candidate_name": "Test Candidate",
                "contact_line": "candidate@example.com",
                "bullets": [
                    {
                        "id": "bullet_api",
                        "text": "Built Python FastAPI workflow automation APIs for internal users.",
                        "tags": ["Python", "FastAPI", "automation"],
                    }
                ],
                "fixed_answers": {
                    "email": "candidate@example.com",
                    "phone": "555-000-0000",
                    "work authorization": "Requires employer sponsorship now or in the future.",
                },
            }
        ),
        encoding="utf-8",
    )
    return str(path)
