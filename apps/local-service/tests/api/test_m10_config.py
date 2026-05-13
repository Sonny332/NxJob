from __future__ import annotations

import json

from fastapi.testclient import TestClient

from nxjob.main import create_app
from nxjob.settings.private_config import (
    private_ai_provider_path,
    private_master_resume_path,
    private_resume_output_path,
)


def test_config_status_reports_missing_private_inputs(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("NXJOB_MASTER_RESUME_PATH", raising=False)
    monkeypatch.delenv("NXJOB_GENERATED_RESUME_DIR", raising=False)
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))

    with TestClient(create_app()) as client:
        response = client.get("/api/v1/config/status")

    assert response.status_code == 200
    body = response.json()
    assert body["master_resume_configured"] is False
    assert body["ai_provider_configured"] is False
    assert body["resume_output_dir_configured"] is False
    assert "Master Resume is not configured." in body["warnings"]
    assert "Resume output folder is not configured." in body["warnings"]


def test_config_can_save_master_resume_and_ai_provider_without_echoing_key(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("NXJOB_MASTER_RESUME_PATH", raising=False)
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))

    master_resume = {
        "id": "master_default",
        "candidate_name": "Candidate",
        "contact_line": "candidate@example.com",
        "bullets": [
            {
                "id": "bullet_api",
                "text": "Built Python FastAPI automation services.",
                "tags": ["Python", "FastAPI"],
            }
        ],
        "fixed_answers": {},
    }

    with TestClient(create_app()) as client:
        master = client.post(
            "/api/v1/config/master-resume",
            json={"content": json.dumps(master_resume), "source_filename": "master.json"},
        )
        ai = client.post(
            "/api/v1/config/ai-provider",
            json={
                "provider": "openai_compatible",
                "base_url": "https://api.example.test/v1",
                "model": "test-model",
                "api_key": "sk-test-secret",
            },
        )
        status = client.get("/api/v1/config/status")
        cleared = client.delete("/api/v1/config/ai-provider")

    assert master.status_code == 200
    assert ai.status_code == 200
    assert status.status_code == 200
    assert "sk-test-secret" not in ai.text
    assert status.json()["master_resume_configured"] is True
    assert status.json()["ai_provider_configured"] is True
    assert status.json()["ai_provider_source"] == "private_config"
    assert private_master_resume_path().exists()
    assert private_ai_provider_path().exists() is False
    assert cleared.json()["ai_provider_configured"] is False


def test_private_ai_provider_takes_priority_over_environment_fallback(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("NXJOB_AI_API_KEY", "sk-env-test-key")
    monkeypatch.setenv("NXJOB_AI_PROVIDER", "deepseek")
    monkeypatch.setenv("NXJOB_AI_MODEL", "env-model")
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))

    with TestClient(create_app()) as client:
        saved = client.post(
            "/api/v1/config/ai-provider",
            json={
                "provider": "gemini",
                "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
                "model": "gemini-3.1-flash-lite",
                "api_key": "sk-private-test-key",
            },
        )
        status = client.get("/api/v1/config/status")
        cleared = client.delete("/api/v1/config/ai-provider")

    assert saved.status_code == 200
    assert status.json()["ai_provider_name"] == "gemini"
    assert status.json()["ai_model"] == "gemini-3.1-flash-lite"
    assert status.json()["ai_provider_source"] == "private_config"
    assert "sk-private-test-key" not in status.text
    assert cleared.json()["ai_provider_name"] == "deepseek"
    assert cleared.json()["ai_model"] == "env-model"
    assert cleared.json()["ai_provider_source"] == "environment"


def test_config_can_save_resume_output_directory(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    monkeypatch.delenv("NXJOB_GENERATED_RESUME_DIR", raising=False)
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))
    output_dir = tmp_path / "generated resumes"

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/v1/config/resume-output-directory",
            json={"path": str(output_dir)},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["resume_output_dir_configured"] is True
    assert body["resume_output_dir"] == str(output_dir)
    assert private_resume_output_path().exists()
