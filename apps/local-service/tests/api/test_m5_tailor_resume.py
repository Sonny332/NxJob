from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from docx import Document
from fastapi.testclient import TestClient

from nxjob.ai.openai_compatible import AiProviderError
from nxjob.db.repositories import new_id, utc_now
from nxjob.main import create_app
from nxjob.schemas.core import TailoredResumeContent
from nxjob.workflows.resume_tailor import TailorDraft


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
    assert body["docx_path"] == body["resume_version"]["file_path"]
    assert body["markdown_path"].endswith(".md")
    assert body["filename_base"].endswith("_resume")
    assert body["layout_budget"]["max_body_lines"] == 55
    assert body["quality_checks"]["summary_avoids_fixed_year_count"] is True

    file_path = Path(body["resume_version"]["file_path"])
    markdown_path = Path(body["markdown_path"])
    assert file_path.exists()
    assert markdown_path.exists()
    assert "Python FastAPI services" in markdown_path.read_text(encoding="utf-8")
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


def test_tailor_resume_uses_configured_ai_provider_without_logging_private_inputs(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "nxjob.sqlite3"
    monkeypatch.setenv("NXJOB_DB_PATH", str(db_path))
    monkeypatch.setenv("NXJOB_GENERATED_RESUME_DIR", str(tmp_path / "generated"))
    monkeypatch.setenv("NXJOB_AI_API_KEY", "sk-private-test-key")
    monkeypatch.setenv("NXJOB_AI_MODEL", "test-tailor-model")

    def fake_ai_tailor(*args, **kwargs):
        ai_config = args[3]
        assert ai_config.api_key == "sk-private-test-key"
        content = TailoredResumeContent(
            candidate_name="Candidate",
            contact_line="candidate@example.com",
            headline="Backend Engineer alignment",
            summary=["Technical professional focused on Python API workflows."],
            skills=["Python", "FastAPI", "SQLite"],
            experience_bullets=["Built Python FastAPI services with SQLite workflow automation."],
            education=["Northeastern University | M.S. | Boston, MA | 2018 - 2020 | GPA: 3.62 / 4.0"],
        )
        return TailorDraft(
            content=content,
            selected_bullet_ids=["bullet_python_api"],
            change_summary="Generated structured resume content with AI provider.",
            token_usage={"prompt_tokens": 100, "completion_tokens": 80, "total_tokens": 180},
            markdown="# Candidate\n",
            layout_budget={"body_lines": 8, "heading_lines": 4, "max_body_lines": 55},
            quality_checks={"one_page_budget_ok": True},
            warnings=[],
        )

    monkeypatch.setattr("nxjob.api.resumes.tailor_resume_content_with_ai", fake_ai_tailor)

    with TestClient(create_app()) as client:
        job_id = _capture_job(
            client,
            "Private JD text for Backend Engineer role using Python APIs.",
        )
        response = client.post(
            "/api/v1/resumes/tailor",
            json={
                "job_lead_id": job_id,
                "master_resume_bullets": [
                    {
                        "id": "bullet_python_api",
                        "text": "Private master resume bullet about Python FastAPI services.",
                        "tags": ["Python", "FastAPI"],
                    }
                ],
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["ai_used"] is True
    assert body["ai_provider_name"] == "openai"

    with sqlite3.connect(db_path) as connection:
        prompt_row = connection.execute(
            """
            SELECT provider, model, input_summary, output_summary, token_usage_json, error
            FROM prompt_logs
            WHERE trace_id = ?
            """,
            (body["trace_id"],),
        ).fetchone()

    serialized_prompt_row = " ".join(str(value) for value in prompt_row)
    assert prompt_row[0] == "openai"
    assert prompt_row[1] == "test-tailor-model"
    assert json.loads(prompt_row[4])["total_tokens"] == 180
    assert "sk-private-test-key" not in serialized_prompt_row
    assert "Private JD text" not in serialized_prompt_row
    assert "Private master resume bullet" not in serialized_prompt_row


def test_tailor_resume_ai_provider_failure_is_sanitized(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "nxjob.sqlite3"
    monkeypatch.setenv("NXJOB_DB_PATH", str(db_path))
    monkeypatch.setenv("NXJOB_GENERATED_RESUME_DIR", str(tmp_path / "generated"))
    monkeypatch.setenv("NXJOB_AI_API_KEY", "sk-private-test-key")
    monkeypatch.setenv("NXJOB_AI_MODEL", "test-tailor-model")

    def fake_ai_tailor(*args, **kwargs):
        raise AiProviderError("authentication_failed", "AI provider authentication failed.", 401)

    monkeypatch.setattr("nxjob.api.resumes.tailor_resume_content_with_ai", fake_ai_tailor)

    with TestClient(create_app()) as client:
        job_id = _capture_job(client, "Private JD text for Python automation role.")
        response = client.post(
            "/api/v1/resumes/tailor",
            json={
                "job_lead_id": job_id,
                "master_resume_bullets": [
                    {
                        "id": "bullet_api",
                        "text": "Private master resume bullet about API automation.",
                        "tags": ["Python", "API"],
                    }
                ],
            },
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "AI provider authentication failed."
    assert "sk-private-test-key" not in response.text

    with sqlite3.connect(db_path) as connection:
        prompt_row = connection.execute(
            "SELECT input_summary, output_summary, error FROM prompt_logs",
        ).fetchone()
        trace_row = connection.execute("SELECT status FROM workflow_traces").fetchone()

    serialized_prompt_row = " ".join(str(value) for value in prompt_row)
    assert prompt_row[2] == "authentication_failed"
    assert trace_row[0] == "failed"
    assert "sk-private-test-key" not in serialized_prompt_row
    assert "Private JD text" not in serialized_prompt_row


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
    assert refreshed.json()["filename_base"].endswith("_v2")


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


def test_tailor_resume_includes_education_years_from_master_resume(tmp_path, monkeypatch) -> None:
    master_path = tmp_path / "master-resume.json"
    master_path.write_text(
        json.dumps(
            {
                "id": "master_default",
                "candidate_name": "Xu (Sonny) Shen",
                "contact_line": "Boston, MA | sonnyshen332@gmail.com",
                "bullets": [
                    {
                        "id": "bullet_python",
                        "text": "Automated Python API workflows for operational reporting.",
                        "tags": ["Python", "API", "automation"],
                    }
                ],
                "education": [
                    {
                        "school": "Northeastern University",
                        "degree": "M.S. in Energy Systems Engineering",
                        "location": "Boston, MA",
                        "start_year": "2018",
                        "end_year": "2020",
                        "gpa": "3.62 / 4.0",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))
    monkeypatch.setenv("NXJOB_GENERATED_RESUME_DIR", str(tmp_path / "generated"))
    monkeypatch.setenv("NXJOB_MASTER_RESUME_PATH", str(master_path))

    with TestClient(create_app()) as client:
        job_id = _capture_job(client, "Python automation role for operational APIs.")
        response = client.post("/api/v1/resumes/tailor", json={"job_lead_id": job_id})

    assert response.status_code == 200
    body = response.json()
    assert body["quality_checks"]["education_years_present"] is True
    markdown = Path(body["markdown_path"]).read_text(encoding="utf-8")
    assert "2018 - 2020" in markdown
    assert "3.62 / 4.0" in markdown


def test_tailor_resume_preserves_structured_experience_timeline(tmp_path, monkeypatch) -> None:
    master_path = tmp_path / "master-resume.json"
    master_path.write_text(
        json.dumps(
            {
                "id": "master_default",
                "candidate_name": "Xu (Sonny) Shen",
                "contact_line": "Boston, MA | sonnyshen332@gmail.com",
                "experience": [
                    {
                        "company": "BostonRen LLC",
                        "location": "Boston, MA",
                        "title": "Operations Analyst",
                        "start_date": "2024",
                        "end_date": "Present",
                        "bullets": [
                            {
                                "id": "exp_current_api",
                                "text": "Automated Python API workflows for operations reporting and issue tracking.",
                                "tags": ["Python", "API", "operations"],
                            }
                        ],
                    },
                    {
                        "company": "Earlier Energy Co",
                        "location": "Shanghai, China",
                        "title": "Project Engineer",
                        "start_date": "2020",
                        "end_date": "2024",
                        "bullets": [
                            {
                                "id": "exp_prior_controls",
                                "text": "Supported field engineering coordination for facility controls projects.",
                                "tags": ["engineering", "controls"],
                            }
                        ],
                    },
                ],
                "education": [
                    {
                        "school": "Northeastern University",
                        "degree": "M.S. in Energy Systems Engineering",
                        "location": "Boston, MA",
                        "start_year": "2018",
                        "end_year": "2020",
                        "gpa": "3.62 / 4.0",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))
    monkeypatch.setenv("NXJOB_GENERATED_RESUME_DIR", str(tmp_path / "generated"))
    monkeypatch.setenv("NXJOB_MASTER_RESUME_PATH", str(master_path))

    with TestClient(create_app()) as client:
        job_id = _capture_job(client, "Python API operations analyst role.")
        response = client.post("/api/v1/resumes/tailor", json={"job_lead_id": job_id})

    assert response.status_code == 200
    body = response.json()
    assert body["quality_checks"]["experience_timeline_preserved"] is True
    markdown = Path(body["markdown_path"]).read_text(encoding="utf-8")
    assert "BostonRen LLC | Boston, MA | Operations Analyst | 2024 - Present" in markdown
    assert "Earlier Energy Co | Shanghai, China | Project Engineer | 2020 - 2024" in markdown
    paragraphs = [paragraph.text for paragraph in Document(body["docx_path"]).paragraphs]
    assert any("BostonRen LLC" in paragraph and "2024 - Present" in paragraph for paragraph in paragraphs)
    assert any("Earlier Energy Co" in paragraph and "2020 - 2024" in paragraph for paragraph in paragraphs)


def test_tailor_resume_requires_configured_output_directory(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))
    monkeypatch.delenv("NXJOB_GENERATED_RESUME_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))

    with TestClient(create_app()) as client:
        job_id = _capture_job(client, "Backend automation role using Python APIs.")
        response = client.post(
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

    assert response.status_code == 422
    assert response.json()["detail"] == "Resume output folder is not configured."


def test_tailor_resume_uses_safe_date_company_job_filename(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))
    monkeypatch.setenv("NXJOB_GENERATED_RESUME_DIR", str(tmp_path / "generated"))

    with TestClient(create_app()) as client:
        captured = client.post(
            "/api/v1/job-leads/capture",
            json={
                "source_url": "https://example.com/jobs/tailor-test",
                "source_site": "company_ats",
                "page_title": "Data/Automation: Engineer* at ACME|Controls?",
                "selected_text": "Data automation role using Python and APIs.",
            },
        )
        job_id = captured.json()["job_lead"]["id"]
        response = client.post(
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

    assert response.status_code == 200
    filename = response.json()["filename_base"]
    assert filename.startswith("20")
    assert filename.endswith("_resume")
    assert not any(character in filename for character in '/\\:*?"<>|')


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
