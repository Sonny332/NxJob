from __future__ import annotations

from dataclasses import asdict
import json
import sqlite3
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from nxjob.main import create_app
from nxjob.schemas.core import FieldContext, JobLeadRecord, MasterResumeBullet, MasterResumeExperience, MasterResumeProfile
from nxjob.settings.private_config import AiProviderConfig
from nxjob.workflows.form_answer_drafter import draft_form_answer


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
    assert body["ai_used"] is False
    assert "FastAPI" in body["draft"]["answer"]
    assert body["draft"]["referenced_bullets"] == ["bullet_api"]
    assert body["draft"]["risk_flags"]


def test_draft_answers_handles_multiple_fields_without_private_prompt_payloads(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "nxjob.sqlite3"
    master_path = _write_master_resume(tmp_path)
    monkeypatch.setenv("NXJOB_DB_PATH", str(db_path))
    monkeypatch.setenv("NXJOB_MASTER_RESUME_PATH", str(master_path))

    with TestClient(create_app()) as client:
        job_id = _capture_job(client)
        response = client.post(
            "/api/v1/forms/draft-answers",
            json={
                "job_lead_id": job_id,
                "fields": [
                    {
                        "field_id": "field_email",
                        "label": "Email",
                        "placeholder": "email@example.com",
                        "input_type": "email",
                    },
                    {
                        "field_id": "field_why",
                        "label": "Why are you interested in this role?",
                        "surrounding_text": "Tell us why this automation platform role is a fit.",
                        "input_type": "textarea",
                    },
                ],
            },
        )

    body = response.json()
    assert response.status_code == 200
    assert body["ai_used"] is False
    assert len(body["drafts"]) == 2
    assert body["drafts"][0]["answer"] == "candidate@example.com"
    assert "FastAPI" in body["drafts"][1]["answer"]
    assert "Review every answer" in body["warnings"][0]

    with sqlite3.connect(db_path) as connection:
        prompt_rows = connection.execute(
            "SELECT input_summary FROM prompt_logs WHERE workflow_name = ?",
            ("draft_form_answer_from_resume_bullets",),
        ).fetchall()

    joined = "\n".join(row[0] for row in prompt_rows)
    assert "candidate@example.com" not in joined
    assert "Automation platform role using Python" not in joined


def test_draft_answer_uses_ai_for_field_specific_open_question(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "nxjob.sqlite3"
    master_path = _write_master_resume(tmp_path)
    monkeypatch.setenv("NXJOB_DB_PATH", str(db_path))
    monkeypatch.setenv("NXJOB_MASTER_RESUME_PATH", str(master_path))
    monkeypatch.setattr(
        "nxjob.api.forms.read_ai_provider_config",
        lambda: AiProviderConfig(
            provider="openai",
            base_url="https://api.openai.com/v1",
            model="test-model",
            api_key="test-key",
        ),
    )

    captured_messages = []

    def fake_request_json_object(_config, messages, timeout_seconds=60):
        captured_messages.extend(messages)
        return SimpleNamespace(
            data={
                "question_text": "Why are you a good fit for this role?",
                "intent": "why_fit",
                "answer_type": "text",
                "answer": "I am a strong fit because I have built FastAPI workflow automation APIs for internal users.",
                "confidence": 0.86,
                "referenced_bullets": ["bullet_api"],
                "risk_flags": ["Review before filling."],
            },
            token_usage={"prompt_tokens": 12, "completion_tokens": 8},
        )

    monkeypatch.setattr("nxjob.workflows.form_answer_drafter.request_json_object", fake_request_json_object)

    with TestClient(create_app()) as client:
        job_id = _capture_job(client)
        response = client.post(
            "/api/v1/forms/draft-answer",
            json={
                "job_lead_id": job_id,
                "field_context": {
                    "label": "Why are you a good fit for this role?",
                    "surrounding_text": "Explain your strongest relevant experience.",
                    "input_type": "textarea",
                },
            },
        )

    body = response.json()
    assert response.status_code == 200
    assert body["ai_used"] is True
    assert body["draft"]["question_text"] == "Why are you a good fit for this role?"
    assert body["draft"]["intent"] == "why_fit"
    assert body["draft"]["confidence"] == 0.86
    assert "strong fit" in body["draft"]["answer"]
    assert body["draft"]["referenced_bullets"] == ["bullet_api"]
    assert "test-key" not in json.dumps(captured_messages)
    assert "Automation platform role using Python" not in json.dumps(captured_messages)


def test_draft_answer_choice_field_requires_matching_option(tmp_path, monkeypatch) -> None:
    master_path = _write_master_resume(tmp_path)
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))
    monkeypatch.setenv("NXJOB_MASTER_RESUME_PATH", str(master_path))
    monkeypatch.setattr(
        "nxjob.api.forms.read_ai_provider_config",
        lambda: AiProviderConfig(
            provider="openai",
            base_url="https://api.openai.com/v1",
            model="test-model",
            api_key="test-key",
        ),
    )

    def fake_request_json_object(_config, _messages, timeout_seconds=60):
        return SimpleNamespace(
            data={
                "question_text": "Preferred work arrangement",
                "intent": "location",
                "answer_type": "single_choice",
                "answer": "I prefer the hybrid option because it matches my location.",
                "option": "Hybrid",
                "confidence": 0.8,
                "referenced_bullets": [],
                "risk_flags": [],
            },
            token_usage={},
        )

    monkeypatch.setattr("nxjob.workflows.form_answer_drafter.request_json_object", fake_request_json_object)

    with TestClient(create_app()) as client:
        job_id = _capture_job(client)
        response = client.post(
            "/api/v1/forms/draft-answer",
            json={
                "job_lead_id": job_id,
                "field_context": {
                    "label": "Preferred work arrangement",
                    "input_type": "select",
                    "options": ["On-site", "Hybrid", "Remote"],
                },
            },
        )

    body = response.json()
    assert response.status_code == 200
    assert body["ai_used"] is True
    assert body["draft"]["answer"] == "Hybrid"
    assert body["draft"]["selected_option"] == "Hybrid"
    assert body["draft"]["answer_type"] == "single_choice"


def test_draft_answer_salary_question_returns_review_warning_without_inventing(tmp_path, monkeypatch) -> None:
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
                    "label": "What are your salary expectations?",
                    "surrounding_text": "Compensation question",
                    "input_type": "text",
                },
            },
        )

    body = response.json()
    assert response.status_code == 200
    assert body["draft"]["intent"] == "salary"
    assert body["draft"]["answer"] == ""
    assert any("salary" in flag.lower() for flag in body["draft"]["risk_flags"])


@pytest.mark.parametrize("sensitive_kind", ["ssn", "password", "eeoc"])
def test_sensitive_field_draft_answer_returns_blank_without_ai_or_resume_evidence(tmp_path, monkeypatch, sensitive_kind: str) -> None:
    master_path = _write_master_resume(tmp_path)
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))
    monkeypatch.setenv("NXJOB_MASTER_RESUME_PATH", str(master_path))
    monkeypatch.setattr(
        "nxjob.api.forms.read_ai_provider_config",
        lambda: AiProviderConfig(
            provider="openai",
            base_url="https://api.openai.com/v1",
            model="test-model",
            api_key="test-key",
        ),
    )

    ai_call_count = 0

    def fail_if_ai_called(_config, _messages, timeout_seconds=60):
        nonlocal ai_call_count
        ai_call_count += 1
        raise AssertionError("AI should not be called for sensitive fields")

    monkeypatch.setattr("nxjob.workflows.form_answer_drafter.request_json_object", fail_if_ai_called)

    with TestClient(create_app()) as client:
        job_id = _capture_job(client)
        response = client.post(
            "/api/v1/forms/draft-answer",
            json={
                "job_lead_id": job_id,
                "field_context": {
                    "field_id": f"{sensitive_kind}_field",
                    "label": f"{sensitive_kind.upper()} field",
                    "question_text": "Provide the requested sensitive information.",
                    "input_type": "text",
                    "sensitive_kind": sensitive_kind,
                },
            },
        )

    body = response.json()
    assert response.status_code == 200
    assert ai_call_count == 0
    assert body["ai_used"] is False
    assert body["draft"]["answer"] == ""
    assert body["draft"]["referenced_bullets"] == []
    assert body["draft"]["selected_option"] == ""
    assert any("sensitive" in flag.lower() for flag in body["draft"]["risk_flags"])
    assert sensitive_kind not in body["draft"]["answer"].lower()


def test_sensitive_batch_fields_return_safe_blank_drafts_without_ai(tmp_path, monkeypatch) -> None:
    master_path = _write_master_resume(tmp_path)
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))
    monkeypatch.setenv("NXJOB_MASTER_RESUME_PATH", str(master_path))
    monkeypatch.setattr(
        "nxjob.api.forms.read_ai_provider_config",
        lambda: AiProviderConfig(
            provider="openai",
            base_url="https://api.openai.com/v1",
            model="test-model",
            api_key="test-key",
        ),
    )

    ai_call_count = 0

    def fail_if_ai_called(_config, _messages, timeout_seconds=60):
        nonlocal ai_call_count
        ai_call_count += 1
        raise AssertionError("AI should not be called for sensitive fields")

    monkeypatch.setattr("nxjob.workflows.form_answer_drafter.request_json_object", fail_if_ai_called)

    with TestClient(create_app()) as client:
        job_id = _capture_job(client)
        response = client.post(
            "/api/v1/forms/draft-answers",
            json={
                "job_lead_id": job_id,
                "fields": [
                    {
                        "field_id": "field_ssn",
                        "label": "Social Security Number",
                        "question_text": "Enter your SSN",
                        "input_type": "text",
                        "sensitive_kind": "ssn",
                    },
                    {
                        "field_id": "field_password",
                        "label": "Account Password",
                        "question_text": "Enter the password used for this site",
                        "input_type": "password",
                        "sensitive_kind": "password",
                    },
                    {
                        "field_id": "field_eeoc",
                        "label": "Voluntary Self Identification",
                        "question_text": "Complete the EEOC questionnaire",
                        "input_type": "select",
                        "options": ["Decline", "Provide"],
                        "sensitive_kind": "eeoc",
                    },
                ],
            },
        )

    body = response.json()
    assert response.status_code == 200
    assert ai_call_count == 0
    assert body["ai_used"] is False
    assert [draft["answer"] for draft in body["drafts"]] == ["", "", ""]
    assert all(draft["referenced_bullets"] == [] for draft in body["drafts"])
    assert all(any("sensitive" in flag.lower() for flag in draft["risk_flags"]) for draft in body["drafts"])


def test_direct_blank_ambiguous_fields_require_manual_review_without_autofill() -> None:
    job_lead = _sample_job_lead_record()
    master_resume = _sample_master_resume_profile(
        {
            "email": "candidate@example.com",
            "phone": "555-000-0000",
            "current location": "Boston, MA",
            "current company": "Acme Robotics",
            "current title": "Senior Automation Engineer",
            "work authorization": "Requires employer sponsorship now or in the future.",
        }
    )

    drafts = [
        draft_form_answer(job_lead, FieldContext(label=label, current_value="", input_type="text"), master_resume, master_resume.bullets)
        for label in [
            "Preferred location",
            "Location",
            "Company",
            "Employer",
            "Company Name",
            "Employer Name",
            "Title",
            "End Date",
            "Employment End Date",
        ]
    ]

    assert [draft.answer for draft in drafts] == ["", "", "", "", "", "", "", "", ""]
    assert all("manual review" in " ".join(draft.risk_flags).lower() for draft in drafts)
    assert all("My relevant experience includes" not in draft.answer for draft in drafts)
    serialized = json.dumps([asdict(draft) for draft in drafts]).lower()
    assert "boston, ma" not in serialized
    assert "acme robotics" not in serialized
    assert "senior automation engineer" not in serialized


def test_direct_company_employer_and_title_keep_current_value_even_when_blank_autofill_is_blocked() -> None:
    job_lead = _sample_job_lead_record()
    master_resume = _sample_master_resume_profile()

    company_drafts = [
        draft_form_answer(
            job_lead,
            FieldContext(label=label, current_value="Acme Robotics", input_type="text"),
            master_resume,
            master_resume.bullets,
        )
        for label in ["Company", "Employer", "Company Name"]
    ]
    title_draft = draft_form_answer(
        job_lead,
        FieldContext(label="Title", current_value="Senior Automation Engineer", input_type="text"),
        master_resume,
        master_resume.bullets,
    )

    assert [draft.answer for draft in company_drafts] == ["Acme Robotics", "Acme Robotics", "Acme Robotics"]
    assert all(draft.risk_flags == [] for draft in company_drafts)
    assert title_draft.answer == "Senior Automation Engineer"
    assert title_draft.risk_flags == []


def test_draft_answers_preserve_current_values_for_simple_profile_and_employment_fields(tmp_path, monkeypatch) -> None:
    master_path = _write_master_resume(tmp_path)
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))
    monkeypatch.setenv("NXJOB_MASTER_RESUME_PATH", str(master_path))

    with TestClient(create_app()) as client:
        job_id = _capture_job(client)
        response = client.post(
            "/api/v1/forms/draft-answers",
            json={
                "job_lead_id": job_id,
                "fields": [
                    {
                        "field_id": "first_name",
                        "label": "First Name",
                        "surrounding_text": "Address Information City State Postal Code Country",
                        "current_value": "Taylor",
                        "input_type": "text",
                    },
                    {
                        "field_id": "last_name",
                        "label": "Last Name",
                        "current_value": "Candidate",
                        "input_type": "text",
                    },
                    {
                        "field_id": "company_name",
                        "label": "Company Name",
                        "current_value": "Acme Robotics",
                        "input_type": "text",
                    },
                    {
                        "field_id": "job_title",
                        "label": "Title",
                        "current_value": "Senior Automation Engineer",
                        "input_type": "text",
                    },
                    {
                        "field_id": "start_date",
                        "label": "Employment Start Date",
                        "current_value": "2021-01-15",
                        "input_type": "date",
                    },
                    {
                        "field_id": "end_date",
                        "label": "Employment End Date",
                        "current_value": "Present",
                        "input_type": "date",
                    },
                ],
            },
        )

    body = response.json()
    assert response.status_code == 200
    assert body["ai_used"] is False
    assert [draft["answer"] for draft in body["drafts"]] == [
        "Taylor",
        "Candidate",
        "Acme Robotics",
        "Senior Automation Engineer",
        "2021-01-15",
        "Present",
    ]
    assert all(not draft["referenced_bullets"] for draft in body["drafts"])


def test_blank_start_date_fields_do_not_autofill_current_experience_start_date(tmp_path, monkeypatch) -> None:
    master_path = _write_master_resume(tmp_path)
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))
    monkeypatch.setenv("NXJOB_MASTER_RESUME_PATH", str(master_path))

    with TestClient(create_app()) as client:
        job_id = _capture_job(client)
        response = client.post(
            "/api/v1/forms/draft-answers",
            json={
                "job_lead_id": job_id,
                "fields": [
                    {
                        "field_id": "start_date_label",
                        "label": "Start Date",
                        "current_value": "",
                        "input_type": "date",
                    },
                    {
                        "field_id": "availability_question",
                        "label": "Availability",
                        "question_text": "When can you start?",
                        "current_value": "",
                        "input_type": "text",
                    },
                ],
            },
        )

    body = response.json()
    assert response.status_code == 200
    assert body["ai_used"] is False
    assert [draft["answer"] for draft in body["drafts"]] == ["", ""]
    assert all("manual review" in " ".join(draft["risk_flags"]).lower() for draft in body["drafts"])
    assert all(
        any(term in " ".join(draft["risk_flags"]).lower() for term in ("start-date", "availability"))
        for draft in body["drafts"]
    )


def test_blank_ambiguous_profile_and_employment_fields_do_not_autofill_current_facts(tmp_path, monkeypatch) -> None:
    master_path = _write_master_resume(
        tmp_path,
        fixed_answers={
            "email": "candidate@example.com",
            "phone": "555-000-0000",
            "current location": "Boston, MA",
            "current company": "Acme Robotics",
            "current title": "Senior Automation Engineer",
            "work authorization": "Requires employer sponsorship now or in the future.",
        },
    )
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))
    monkeypatch.setenv("NXJOB_MASTER_RESUME_PATH", str(master_path))
    monkeypatch.setattr(
        "nxjob.api.forms.read_ai_provider_config",
        lambda: AiProviderConfig(
            provider="openai",
            base_url="https://api.openai.com/v1",
            model="test-model",
            api_key="test-key",
        ),
    )

    ai_call_count = 0

    def fail_if_ai_called(_config, _messages, timeout_seconds=60):
        nonlocal ai_call_count
        ai_call_count += 1
        raise AssertionError("AI should not be called for blank ambiguous profile or employment fields")

    monkeypatch.setattr("nxjob.workflows.form_answer_drafter.request_json_object", fail_if_ai_called)

    with TestClient(create_app()) as client:
        job_id = _capture_job(client)
        response = client.post(
            "/api/v1/forms/draft-answers",
            json={
                "job_lead_id": job_id,
                "fields": [
                    {
                        "field_id": "preferred_location",
                        "label": "Preferred location",
                        "current_value": "",
                        "input_type": "text",
                    },
                    {
                        "field_id": "location",
                        "label": "Location",
                        "current_value": "",
                        "input_type": "text",
                    },
                    {
                        "field_id": "company",
                        "label": "Company",
                        "current_value": "",
                        "input_type": "text",
                    },
                    {
                        "field_id": "employer",
                        "label": "Employer",
                        "current_value": "",
                        "input_type": "text",
                    },
                    {
                        "field_id": "company_name",
                        "label": "Company Name",
                        "current_value": "",
                        "input_type": "text",
                    },
                    {
                        "field_id": "employer_name",
                        "label": "Employer Name",
                        "current_value": "",
                        "input_type": "text",
                    },
                    {
                        "field_id": "title",
                        "label": "Title",
                        "current_value": "",
                        "input_type": "text",
                    },
                    {
                        "field_id": "end_date",
                        "label": "End Date",
                        "current_value": "",
                        "input_type": "date",
                    },
                    {
                        "field_id": "employment_end_date",
                        "label": "Employment End Date",
                        "current_value": "",
                        "input_type": "date",
                    },
                ],
            },
        )

    body = response.json()
    assert response.status_code == 200
    assert ai_call_count == 0
    assert body["ai_used"] is False
    assert [draft["answer"] for draft in body["drafts"]] == ["", "", "", "", "", "", "", "", ""]
    assert all("manual review" in " ".join(draft["risk_flags"]).lower() for draft in body["drafts"])
    assert all("My relevant experience includes" not in draft["answer"] for draft in body["drafts"])
    assert "boston, ma" not in json.dumps(body).lower()
    assert "acme robotics" not in json.dumps(body).lower()
    assert "senior automation engineer" not in json.dumps(body).lower()


def test_open_question_with_state_word_does_not_backfill_state_field(tmp_path, monkeypatch) -> None:
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
                    "label": "Please state why you are interested",
                    "input_type": "textarea",
                },
            },
        )

    body = response.json()
    assert response.status_code == 200
    assert body["ai_used"] is False
    assert body["draft"]["answer"] != "Massachusetts"


def test_open_question_with_address_verb_does_not_backfill_street_address(tmp_path, monkeypatch) -> None:
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
                    "label": "How would you address a difficult customer issue?",
                    "input_type": "textarea",
                },
            },
        )

    body = response.json()
    assert response.status_code == 200
    assert body["ai_used"] is False
    assert body["draft"]["answer"] != "123 Main Street"


def test_open_question_with_employer_phrase_does_not_backfill_current_company(tmp_path, monkeypatch) -> None:
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
                    "label": "Previous employer details",
                    "input_type": "textarea",
                },
            },
        )

    body = response.json()
    assert response.status_code == 200
    assert body["ai_used"] is False
    assert body["draft"]["answer"] != "Acme Robotics"


def test_work_authorization_choice_field_uses_work_authorization_fixed_key(tmp_path, monkeypatch) -> None:
    master_path = _write_master_resume(
        tmp_path,
        fixed_answers={
            "email": "candidate@example.com",
            "phone": "555-000-0000",
            "work authorization": "Legally authorized to work in the United States.",
        },
    )
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))
    monkeypatch.setenv("NXJOB_MASTER_RESUME_PATH", str(master_path))

    with TestClient(create_app()) as client:
        job_id = _capture_job(client)
        response = client.post(
            "/api/v1/forms/draft-answer",
            json={
                "job_lead_id": job_id,
                "field_context": {
                    "label": "Are you legally authorized to work in the United States?",
                    "input_type": "radio",
                    "options": ["Yes", "No"],
                },
            },
        )

    body = response.json()
    assert response.status_code == 200
    assert body["ai_used"] is False
    assert body["draft"]["answer"] == "Yes"


def test_simple_field_noise_does_not_turn_first_name_into_resume_summary(tmp_path, monkeypatch) -> None:
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
                    "label": "First Name",
                    "question_text": "First Name",
                    "placeholder": "Enter first name",
                    "surrounding_text": (
                        "Current Address Current Location City State Postal Code Country "
                        "Employment History Company Name Title"
                    ),
                    "current_value": "Taylor",
                    "input_type": "text",
                },
            },
        )

    body = response.json()
    assert response.status_code == 200
    assert body["ai_used"] is False
    assert body["draft"]["answer"] == "Taylor"
    assert "My relevant experience includes" not in body["draft"]["answer"]


def test_work_authorization_question_does_not_reuse_sponsorship_fact_as_answer(tmp_path, monkeypatch) -> None:
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
                    "label": "Are you legally authorized to work in the United States?",
                    "surrounding_text": "Answer this work authorization question.",
                    "input_type": "text",
                },
            },
        )

    body = response.json()
    assert response.status_code == 200
    assert body["draft"]["answer"] != "Requires employer sponsorship now or in the future."
    assert any("manual review" in flag.lower() for flag in body["draft"]["risk_flags"])


def test_sponsorship_choice_field_maps_fixed_fact_to_option(tmp_path, monkeypatch) -> None:
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
                    "label": "Will you now or in the future require visa sponsorship?",
                    "input_type": "radio",
                    "options": ["Yes", "No"],
                },
            },
        )

    body = response.json()
    assert response.status_code == 200
    assert body["ai_used"] is False
    assert body["draft"]["answer"] == "Yes"


def test_sponsorship_choice_field_maps_negative_fixed_fact_to_option(tmp_path, monkeypatch) -> None:
    master_path = _write_master_resume(
        tmp_path,
        fixed_answers={
            "email": "candidate@example.com",
            "phone": "555-000-0000",
            "work authorization": "I will not require employer sponsorship now or in the future.",
        },
    )
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))
    monkeypatch.setenv("NXJOB_MASTER_RESUME_PATH", str(master_path))

    with TestClient(create_app()) as client:
        job_id = _capture_job(client)
        response = client.post(
            "/api/v1/forms/draft-answer",
            json={
                "job_lead_id": job_id,
                "field_context": {
                    "label": "Will you now or in the future require visa sponsorship?",
                    "input_type": "radio",
                    "options": ["Yes", "No"],
                },
            },
        )

    body = response.json()
    assert response.status_code == 200
    assert body["ai_used"] is False
    assert body["draft"]["answer"] == "No"


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


def _sample_job_lead_record() -> JobLeadRecord:
    return JobLeadRecord(
        id="job_test",
        source_url="https://example.com/jobs/form-answer",
        source_site="company_ats",
        page_title="Automation Platform Engineer",
        company_name="Example Co",
        job_title="Automation Platform Engineer",
        location="Remote",
        captured_at="2026-05-21T00:00:00Z",
        jd_text="Automation platform role using Python, FastAPI, and workflow APIs.",
        jd_hash="hash_test",
        platform_insights={},
        search_query="",
        status="new",
        user_notes="",
    )


def _sample_master_resume_profile(fixed_answers: dict[str, str] | None = None) -> MasterResumeProfile:
    return MasterResumeProfile(
        id="master_test",
        candidate_name="Test Candidate",
        contact_line="candidate@example.com",
        bullets=[
            MasterResumeBullet(
                id="bullet_api",
                text="Built Python FastAPI workflow automation APIs for internal users.",
                tags=["Python", "FastAPI", "automation"],
            )
        ],
        experience=[
            MasterResumeExperience(
                company="Acme Robotics",
                location="Boston, MA",
                title="Senior Automation Engineer",
                start_date="2021-01-15",
                end_date="Present",
                bullets=[],
            )
        ],
        fixed_answers=fixed_answers
        or {
            "email": "candidate@example.com",
            "phone": "555-000-0000",
            "first name": "Taylor",
            "last name": "Candidate",
            "full name": "Taylor Candidate",
            "address": "123 Main Street",
            "city": "Boston",
            "state": "Massachusetts",
            "postal code": "02110",
            "country": "United States",
            "current company": "Acme Robotics",
            "current title": "Senior Automation Engineer",
            "work authorization": "Requires employer sponsorship now or in the future.",
        },
    )


def _write_master_resume(tmp_path, fixed_answers: dict[str, str] | None = None) -> str:
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
                "experience": [
                    {
                        "company": "Acme Robotics",
                        "location": "Boston, MA",
                        "title": "Senior Automation Engineer",
                        "start_date": "2021-01-15",
                        "end_date": "Present",
                        "bullets": [],
                    }
                ],
                "fixed_answers": fixed_answers
                or {
                    "email": "candidate@example.com",
                    "phone": "555-000-0000",
                    "first name": "Taylor",
                    "last name": "Candidate",
                    "full name": "Taylor Candidate",
                    "address": "123 Main Street",
                    "city": "Boston",
                    "state": "Massachusetts",
                    "postal code": "02110",
                    "country": "United States",
                    "current company": "Acme Robotics",
                    "current title": "Senior Automation Engineer",
                    "work authorization": "Requires employer sponsorship now or in the future.",
                },
            }
        ),
        encoding="utf-8",
    )
    return str(path)
