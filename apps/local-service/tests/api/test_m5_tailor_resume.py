from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from docx import Document
from fastapi.testclient import TestClient

from nxjob.db.repositories import new_id, utc_now
from nxjob.main import create_app


def test_tailor_resume_generates_docx_and_resume_version(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "nxjob.sqlite3"
    output_dir = tmp_path / "generated"
    monkeypatch.setenv("NXJOB_DB_PATH", str(db_path))
    monkeypatch.setenv("NXJOB_GENERATED_RESUME_DIR", str(output_dir))

    with TestClient(create_app()) as client:
        job_id = _capture_job(
            client,
            "Backend Engineer role using Python, FastAPI, SQLite, automation, and API workflows.",
        )
        response = client.post(
            "/api/v1/resumes/tailor",
            json={
                "job_lead_id": job_id,
                "master_resume_id": "master_default",
                "master_resume_bullets": [
                    {
                        "id": "bullet_python_api",
                        "text": "Built Python FastAPI services with SQLite-backed workflow automation.",
                        "tags": ["Python", "FastAPI", "SQLite", "automation"],
                    },
                    {
                        "id": "bullet_frontend",
                        "text": "Improved React popup UI for browser extension workflows.",
                        "tags": ["React", "TypeScript"],
                    },
                ],
                "constraints": {
                    "format": "docx",
                    "target_length": "one_page_preferred",
                    "ats_friendly": True,
                },
                "success_reference_limit": 3,
            },
        )

    body = response.json()
    assert response.status_code == 200
    assert body["trace_id"].startswith("trc_")
    assert body["resume_version"]["format"] == "docx"
    assert body["resume_version"]["selected_bullets"][0] == "bullet_python_api"
    assert "Selected" in body["resume_version"]["change_summary"]

    file_path = Path(body["resume_version"]["file_path"])
    assert file_path.exists()
    paragraphs = [paragraph.text for paragraph in Document(file_path).paragraphs]
    assert any("Python FastAPI services" in text for text in paragraphs)

    with sqlite3.connect(db_path) as connection:
        prompt_row = connection.execute(
            "SELECT provider, token_usage_json FROM prompt_logs WHERE trace_id = ?",
            (body["trace_id"],),
        ).fetchone()
        resume_row = connection.execute(
            "SELECT status FROM job_leads WHERE id = ?",
            (job_id,),
        ).fetchone()

    assert prompt_row[0] == "local_stub"
    assert json.loads(prompt_row[1])["input_chars"] > 0
    assert resume_row[0] == "tailored"


def test_tailor_resume_reuses_cache_and_can_force_refresh(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))
    monkeypatch.setenv("NXJOB_GENERATED_RESUME_DIR", str(tmp_path / "generated"))

    with TestClient(create_app()) as client:
        job_id = _capture_job(client, "Data automation role using Python and APIs.")
        payload = {
            "job_lead_id": job_id,
            "master_resume_bullets": [
                {
                    "id": "bullet_api",
                    "text": "Automated API workflows with Python services.",
                    "tags": ["Python", "API"],
                }
            ],
        }
        first = client.post("/api/v1/resumes/tailor", json=payload)
        second = client.post("/api/v1/resumes/tailor", json=payload)
        refreshed = client.post(
            "/api/v1/resumes/tailor",
            json={**payload, "force_refresh": True},
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert refreshed.status_code == 200
    assert first.json()["cache"]["hit"] is False
    assert second.json()["cache"]["hit"] is True
    assert refreshed.json()["cache"]["hit"] is False
    assert first.json()["resume_version"]["id"] == second.json()["resume_version"]["id"]
    assert refreshed.json()["resume_version"]["id"] != first.json()["resume_version"]["id"]


def test_tailor_resume_uses_success_references(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "nxjob.sqlite3"
    monkeypatch.setenv("NXJOB_DB_PATH", str(db_path))
    monkeypatch.setenv("NXJOB_GENERATED_RESUME_DIR", str(tmp_path / "generated"))

    with TestClient(create_app()) as client:
        job_id = _capture_job(client, "Platform role with FastAPI and workflow automation.")
        _insert_success_reference(db_path, job_id, ["fastapi", "automation"])
        response = client.post(
            "/api/v1/resumes/tailor",
            json={
                "job_lead_id": job_id,
                "master_resume_bullets": [
                    {
                        "id": "bullet_success_overlap",
                        "text": "Shipped FastAPI automation workflows for internal platforms.",
                        "tags": ["FastAPI", "automation"],
                    }
                ],
                "success_reference_limit": 2,
            },
        )

    assert response.status_code == 200
    assert response.json()["used_success_references"] == ["sref_test"]


def test_tailor_resume_feedback_is_saved(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))
    monkeypatch.setenv("NXJOB_GENERATED_RESUME_DIR", str(tmp_path / "generated"))

    with TestClient(create_app()) as client:
        job_id = _capture_job(client, "Backend automation role using Python APIs.")
        tailored = client.post(
            "/api/v1/resumes/tailor",
            json={
                "job_lead_id": job_id,
                "master_resume_bullets": [
                    {
                        "id": "bullet_api",
                        "text": "Automated API workflows with Python services.",
                        "tags": ["Python", "API"],
                    }
                ],
            },
        )
        response = client.post(
            "/api/v1/resumes/feedback",
            json={
                "job_lead_id": job_id,
                "resume_version_id": tailored.json()["resume_version"]["id"],
                "rating": "good_fit",
                "user_notes": "Strong enough for MVP.",
            },
        )

    assert response.status_code == 200
    assert response.json()["feedback"]["id"].startswith("rfb_")
    assert response.json()["feedback"]["rating"] == "good_fit"


def _capture_job(client: TestClient, jd_text: str) -> str:
    response = client.post(
        "/api/v1/job-leads/capture",
        json={
            "source_url": "https://example.com/jobs/tailor-test",
            "source_site": "company_ats",
            "page_title": "Tailor test",
            "selected_text": jd_text,
        },
    )
    assert response.status_code == 200
    return response.json()["job_lead"]["id"]


def _insert_success_reference(db_path: Path, job_id: str, keywords: list[str]) -> None:
    resume_id = new_id("res")
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO resume_versions (
              id, job_lead_id, source_master_resume_id, created_at, format, file_path
            )
            VALUES (?, ?, 'master_default', ?, 'docx', ?)
            """,
            (resume_id, job_id, utc_now(), "D:/tmp/success.docx"),
        )
        connection.execute(
            """
            INSERT INTO success_references (
              id, job_lead_id, resume_version_id, outcome_type, outcome_at, source,
              effective_keywords_json, effective_bullets_json
            )
            VALUES ('sref_test', ?, ?, 'screen', ?, 'manual', ?, ?)
            """,
            (
                job_id,
                resume_id,
                utc_now(),
                json.dumps(keywords),
                json.dumps(["bullet_success_overlap"]),
            ),
        )
        connection.commit()
