from __future__ import annotations

import sqlite3
import json

from fastapi.testclient import TestClient

from nxjob.main import create_app


def test_sponsorship_explicit_support_uses_local_rules(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "nxjob.sqlite3"
    monkeypatch.setenv("NXJOB_DB_PATH", str(db_path))

    with TestClient(create_app()) as client:
        job_id = _capture_job(
            client,
            "Software Engineer. Visa sponsorship is available for qualified candidates.",
        )

        response = client.post(
            "/api/v1/sponsorship/analyze",
            json={"job_lead_id": job_id, "allow_ai": True},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["trace_id"].startswith("trc_")
    assert body["sponsorship"]["status"] == "supports"
    assert body["sponsorship"]["is_legal_conclusion"] is False
    assert body["ai_used"] is False
    assert body["evidence"][0]["source"] == "jd_text"

    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "SELECT status, source FROM sponsorship_evidence WHERE job_lead_id = ?",
            (job_id,),
        ).fetchall()

    assert rows == [("supports", "jd_text")]


def test_sponsorship_explicit_rejection_uses_local_rules(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))

    with TestClient(create_app()) as client:
        job_id = _capture_job(client, "Applicants must be authorized. We do not sponsor visas.")
        response = client.post(
            "/api/v1/sponsorship/analyze",
            json={"job_lead_id": job_id, "allow_ai": True},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["sponsorship"]["status"] == "does_not_support"
    assert body["ai_used"] is False


def test_sponsorship_not_eligible_for_visa_sponsorship_uses_local_rules(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))

    with TestClient(create_app()) as client:
        job_id = _capture_job(client, "This role is not eligible for Visa Sponsorship.")
        response = client.post(
            "/api/v1/sponsorship/analyze",
            json={"job_lead_id": job_id, "allow_ai": True},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["sponsorship"]["status"] == "does_not_support"
    assert body["ai_used"] is False


class FakeAiResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_sponsorship_ambiguous_text_reports_missing_ai_config(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))
    monkeypatch.delenv("NXJOB_AI_API_KEY", raising=False)

    with TestClient(create_app()) as client:
        job_id = _capture_job(client, "Candidates must be authorized to work in the United States.")
        response = client.post(
            "/api/v1/sponsorship/analyze",
            json={"job_lead_id": job_id, "allow_ai": True},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["sponsorship"]["status"] == "needs_confirmation"
    assert body["ai_used"] is False
    assert any(item["source"] == "ai_config_missing" for item in body["evidence"])


def test_sponsorship_ambiguous_text_uses_configured_ai_provider(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "nxjob.sqlite3"
    monkeypatch.setenv("NXJOB_DB_PATH", str(db_path))
    monkeypatch.setenv("NXJOB_AI_API_KEY", "test-api-key-secret")
    monkeypatch.setenv("NXJOB_AI_PROVIDER", "openai_compatible")
    monkeypatch.setenv("NXJOB_AI_BASE_URL", "https://api.example.test/v1")
    monkeypatch.setenv("NXJOB_AI_MODEL", "test-model")

    def fake_urlopen(request, timeout):
        request_body = json.loads(request.data.decode("utf-8"))
        assert request.get_header("Authorization") == "Bearer test-api-key-secret"
        assert request_body["model"] == "test-model"
        return FakeAiResponse(
            {
                "model": "test-model",
                "usage": {"total_tokens": 123},
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "status": "likely_not_supports",
                                    "confidence": 0.72,
                                    "summary": "The JD requires work authorization but does not confirm sponsorship.",
                                    "evidence": "Authorized to work in the United States.",
                                    "risk_flags": ["Work authorization language is ambiguous."],
                                    "questions_to_confirm": ["Can the employer sponsor this role?"],
                                }
                            )
                        }
                    }
                ],
            }
        )

    monkeypatch.setattr("nxjob.ai.openai_compatible.urlopen", fake_urlopen)

    with TestClient(create_app()) as client:
        job_id = _capture_job(client, "Candidates must be authorized to work in the United States.")
        response = client.post(
            "/api/v1/sponsorship/analyze",
            json={"job_lead_id": job_id, "allow_ai": True},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["sponsorship"]["status"] == "likely_not_supports"
    assert body["ai_used"] is True
    assert any(item["source"] == "ai_inference" for item in body["evidence"])

    with sqlite3.connect(db_path) as connection:
        prompt_log = connection.execute(
            "SELECT input_summary, model, provider, error FROM prompt_logs WHERE workflow_name = ?",
            ("analyze_sponsorship",),
        ).fetchone()

    assert prompt_log == ("JD sponsorship indicators only; full JD not logged", "test-model", "openai", "")
    assert "test-api-key-secret" not in response.text


def test_sponsorship_can_disable_ai_fallback(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))

    with TestClient(create_app()) as client:
        job_id = _capture_job(client, "Candidates must be authorized to work in the United States.")
        response = client.post(
            "/api/v1/sponsorship/analyze",
            json={"job_lead_id": job_id, "allow_ai": False},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["sponsorship"]["status"] == "needs_confirmation"
    assert body["ai_used"] is False
    assert body["evidence"][0]["source"] == "jd_text"


def test_sponsorship_reuses_cached_result_by_default(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "nxjob.sqlite3"
    monkeypatch.setenv("NXJOB_DB_PATH", str(db_path))

    with TestClient(create_app()) as client:
        job_id = _capture_job(
            client,
            "Software Engineer. Visa sponsorship is available for qualified candidates.",
        )
        first = client.post(
            "/api/v1/sponsorship/analyze",
            json={"job_lead_id": job_id, "allow_ai": True},
        )
        second = client.post(
            "/api/v1/sponsorship/analyze",
            json={"job_lead_id": job_id, "allow_ai": True},
        )
        refreshed = client.post(
            "/api/v1/sponsorship/analyze",
            json={"job_lead_id": job_id, "allow_ai": True, "force_refresh": True},
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert refreshed.status_code == 200
    assert first.json()["cache"]["hit"] is False
    assert second.json()["cache"]["hit"] is True
    assert refreshed.json()["cache"]["hit"] is False
    assert second.json()["trace_id"] == first.json()["trace_id"]
    assert refreshed.json()["trace_id"] != first.json()["trace_id"]

    with sqlite3.connect(db_path) as connection:
        evidence_count = connection.execute(
            "SELECT COUNT(*) FROM sponsorship_evidence WHERE job_lead_id = ?",
            (job_id,),
        ).fetchone()[0]

    assert evidence_count == 2


def _capture_job(client: TestClient, jd_text: str) -> str:
    response = client.post(
        "/api/v1/job-leads/capture",
        json={
            "source_url": "https://example.com/jobs/sponsorship-test",
            "source_site": "company_ats",
            "page_title": "Sponsorship test",
            "selected_text": jd_text,
        },
    )
    assert response.status_code == 200
    return response.json()["job_lead"]["id"]
