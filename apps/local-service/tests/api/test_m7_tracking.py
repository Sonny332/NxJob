from __future__ import annotations

from fastapi.testclient import TestClient

from nxjob.main import create_app


def test_positive_outcome_creates_success_reference(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))

    with TestClient(create_app()) as client:
        job_id = _capture_job(client)
        resume_id = _create_resume_version(client, job_id)
        application_id = _create_application(client, job_id, resume_id)

        response = client.post(
            "/api/v1/outcomes",
            json={
                "application_id": application_id,
                "job_lead_id": job_id,
                "outcome_type": "screen",
                "outcome_at": "2026-05-07T12:00:00+00:00",
                "source": "manual",
                "evidence_text": "Recruiter requested a phone screen.",
                "user_notes": "High signal.",
            },
        )

        body = response.json()
        success_id = body["success_reference"]["id"]
        detail = client.get(f"/api/v1/success-references/{success_id}")
        read_application = client.get(f"/api/v1/applications/{application_id}")
        read_job = client.get(f"/api/v1/job-leads/{job_id}")

    assert response.status_code == 200
    assert body["outcome"]["outcome_type"] == "screen"
    assert body["success_reference"]["created"] is True
    assert success_id.startswith("sref_")
    assert detail.status_code == 200
    detail_body = detail.json()["detail"]
    assert detail_body["success_reference"]["resume_version_id"] == resume_id
    assert detail_body["success_reference"]["effective_bullets"] == ["bullet_api"]
    assert detail_body["job_lead"]["search_query"] == "python fastapi automation"
    assert detail_body["application"]["id"] == application_id
    assert read_application.json()["status"] == "interviewing"
    assert read_job.json()["status"] == "interviewing"


def test_rejection_outcome_does_not_create_success_reference(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))

    with TestClient(create_app()) as client:
        job_id = _capture_job(client)
        resume_id = _create_resume_version(client, job_id)
        application_id = _create_application(client, job_id, resume_id)

        response = client.post(
            "/api/v1/outcomes",
            json={
                "application_id": application_id,
                "job_lead_id": job_id,
                "outcome_type": "rejection",
                "source": "manual",
                "evidence_text": "Rejected by email.",
            },
        )
        references = client.get("/api/v1/success-references")

    assert response.status_code == 200
    assert response.json()["success_reference"] == {"created": False, "id": ""}
    assert references.status_code == 200
    assert references.json()["success_references"] == []


def test_application_accepts_side_panel_manual_method(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))

    with TestClient(create_app()) as client:
        job_id = _capture_job(client)
        resume_id = _create_resume_version(client, job_id)

        response = client.post(
            "/api/v1/applications",
            json={
                "job_lead_id": job_id,
                "resume_version_id": resume_id,
                "application_url": "https://example.com/apply/manual",
                "application_method": "manual",
                "submitted_by_user": True,
            },
        )

    assert response.status_code == 200
    assert response.json()["application"]["application_method"] == "manual"
    assert response.json()["application"]["submitted_by_user"] is True


def test_positive_outcome_without_application_uses_latest_resume_version(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))

    with TestClient(create_app()) as client:
        job_id = _capture_job(client)
        resume_id = _create_resume_version(client, job_id)

        response = client.post(
            "/api/v1/outcomes",
            json={
                "job_lead_id": job_id,
                "outcome_type": "screen",
                "source": "manual",
                "evidence_text": "Screen received, application id not recorded.",
            },
        )
        success_id = response.json()["success_reference"]["id"]
        detail = client.get(f"/api/v1/success-references/{success_id}")

    assert response.status_code == 200
    assert response.json()["success_reference"]["created"] is True
    assert detail.json()["detail"]["success_reference"]["resume_version_id"] == resume_id
    assert detail.json()["detail"]["application"] is None


def test_tailor_resume_uses_success_reference_created_from_outcome(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))
    monkeypatch.setenv("NXJOB_GENERATED_RESUME_DIR", str(tmp_path / "generated"))

    with TestClient(create_app()) as client:
        success_job_id = _capture_job(client)
        success_resume_id = _create_resume_version(client, success_job_id)
        success_application_id = _create_application(client, success_job_id, success_resume_id)
        outcome = client.post(
            "/api/v1/outcomes",
            json={
                "application_id": success_application_id,
                "job_lead_id": success_job_id,
                "outcome_type": "positive_reply",
                "source": "manual",
            },
        )
        success_id = outcome.json()["success_reference"]["id"]

        target_job_id = _capture_job(client, url_suffix="target")
        response = client.post(
            "/api/v1/resumes/tailor",
            json={
                "job_lead_id": target_job_id,
                "master_resume_bullets": [
                    {
                        "id": "bullet_api",
                        "text": "Built Python FastAPI automation APIs for internal workflows.",
                        "tags": ["Python", "FastAPI", "automation"],
                    }
                ],
                "success_reference_limit": 3,
            },
        )

    assert response.status_code == 200
    assert response.json()["used_success_references"] == [success_id]


def _capture_job(client: TestClient, url_suffix: str = "tracking") -> str:
    response = client.post(
        "/api/v1/job-leads/capture",
        json={
            "source_url": f"https://example.com/jobs/{url_suffix}",
            "source_site": "company_ats",
            "page_title": "Platform Engineer",
            "selected_text": "Python FastAPI automation platform role with workflow APIs.",
            "search_query": "python fastapi automation",
        },
    )
    assert response.status_code == 200
    return response.json()["job_lead"]["id"]


def _create_resume_version(client: TestClient, job_id: str) -> str:
    response = client.post(
        "/api/v1/resume-versions",
        json={
            "job_lead_id": job_id,
            "source_master_resume_id": "master_test",
            "file_path": "D:/tmp/resume.docx",
            "selected_bullets": ["bullet_api"],
            "change_summary": "Focused on API automation.",
        },
    )
    assert response.status_code == 200
    return response.json()["resume_version"]["id"]


def _create_application(client: TestClient, job_id: str, resume_id: str) -> str:
    response = client.post(
        "/api/v1/applications",
        json={
            "job_lead_id": job_id,
            "resume_version_id": resume_id,
            "application_url": "https://example.com/apply/tracking",
            "application_method": "external_ats",
            "submitted_by_user": True,
        },
    )
    assert response.status_code == 200
    return response.json()["application"]["id"]
