from __future__ import annotations

import sqlite3

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


def test_sponsorship_ambiguous_text_uses_ai_fallback_stub(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))

    with TestClient(create_app()) as client:
        job_id = _capture_job(client, "Candidates must be authorized to work in the United States.")
        response = client.post(
            "/api/v1/sponsorship/analyze",
            json={"job_lead_id": job_id, "allow_ai": True},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["sponsorship"]["status"] == "needs_confirmation"
    assert body["ai_used"] is True
    assert any(item["source"] == "ai_inference" for item in body["evidence"])


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
