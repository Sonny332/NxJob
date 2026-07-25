from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

from nxjob.main import create_app


def test_form_answer_library_empty_read_returns_versioned_payload() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/form-answer-library")

    assert response.status_code == 200
    body = response.json()
    assert body["trace_id"]
    assert body["version"] == 1
    assert body["answers"] == []


def test_form_answer_library_crud_round_trip() -> None:
    with TestClient(create_app()) as client:
        create_response = client.post(
            "/api/v1/form-answer-library",
            json={
                "question": "  Are you legally authorized to work in the United States?  ",
                "fieldType": "select",
                "answers": [" Yes "],
                "sensitive": True,
            },
        )
        created = create_response.json()["answer"]
        read_response = client.get("/api/v1/form-answer-library")
        update_response = client.put(
            f"/api/v1/form-answer-library/{created['id']}",
            json={"answers": ["No"], "sensitive": True},
        )
        touched_response = client.post(f"/api/v1/form-answer-library/{created['id']}/touch")
        delete_response = client.delete(f"/api/v1/form-answer-library/{created['id']}")
        missing_response = client.delete("/api/v1/form-answer-library/missing-answer")

    assert create_response.status_code == 200
    assert created["question"] == "Are you legally authorized to work in the United States?"
    assert created["normalizedQuestion"] == "are you legally authorized to work in the united states"
    assert created["fieldType"] == "select"
    assert created["answers"] == ["Yes"]
    assert created["sensitive"] is True
    assert created["createdAt"]
    assert created["updatedAt"]
    assert created["lastUsedAt"]

    assert read_response.status_code == 200
    assert read_response.json()["answers"] == [created]

    assert update_response.status_code == 200
    updated = update_response.json()["answer"]
    assert updated["id"] == created["id"]
    assert updated["answers"] == ["No"]
    assert updated["updatedAt"] >= created["updatedAt"]
    assert updated["lastUsedAt"] >= created["lastUsedAt"]

    assert touched_response.status_code == 200
    touched = touched_response.json()["answer"]
    assert touched["id"] == created["id"]
    assert touched["answers"] == ["No"]
    assert touched["lastUsedAt"] >= updated["lastUsedAt"]

    assert delete_response.status_code == 200
    assert delete_response.json()["trace_id"]
    assert missing_response.status_code == 404


def test_form_answer_library_create_dedupes_by_question_field_type_and_answers() -> None:
    with TestClient(create_app()) as client:
        first_response = client.post(
            "/api/v1/form-answer-library",
            json={
                "question": "  Are you legally authorized to work in the United States?  ",
                "fieldType": "radio",
                "answers": [" Yes "],
                "sensitive": False,
            },
        )
        second_response = client.post(
            "/api/v1/form-answer-library",
            json={
                "question": "Are you legally authorized to work in the United States?",
                "fieldType": "radio",
                "answers": ["Yes"],
                "sensitive": True,
            },
        )
        read_response = client.get("/api/v1/form-answer-library")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    first = first_response.json()["answer"]
    second = second_response.json()["answer"]
    answers = read_response.json()["answers"]

    assert len(answers) == 1
    assert second["id"] == first["id"]
    assert second["createdAt"] == first["createdAt"]
    assert second["question"] == "Are you legally authorized to work in the United States?"
    assert second["sensitive"] is True
    assert second["updatedAt"] >= first["updatedAt"]
    assert second["lastUsedAt"] >= first["lastUsedAt"]


def test_form_answer_library_import_is_idempotent() -> None:
    payload = {
        "version": 1,
        "answers": [
            {
                "id": "legacy-1",
                "question": "Do you now or will you in the future require visa sponsorship?",
                "normalizedQuestion": "wrong-value",
                "fieldType": "radio",
                "answers": [" Yes "],
                "sensitive": False,
                "createdAt": "2026-07-01T00:00:00Z",
                "updatedAt": "2026-07-02T00:00:00Z",
                "lastUsedAt": "2026-07-03T00:00:00Z",
            },
            {
                "id": "legacy-2",
                "question": "  Do you now or will you in the future require visa sponsorship? ",
                "normalizedQuestion": "still-wrong",
                "fieldType": "radio",
                "answers": ["Yes"],
                "sensitive": True,
                "createdAt": "2026-07-04T00:00:00Z",
                "updatedAt": "2026-07-05T00:00:00Z",
                "lastUsedAt": "2026-07-06T00:00:00Z",
            },
        ],
    }

    with TestClient(create_app()) as client:
        first_response = client.post("/api/v1/form-answer-library/import", json=payload)
        second_response = client.post("/api/v1/form-answer-library/import", json=payload)
        read_response = client.get("/api/v1/form-answer-library")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert read_response.status_code == 200

    answers = read_response.json()["answers"]
    assert len(answers) == 1
    assert answers[0]["question"] == "Do you now or will you in the future require visa sponsorship?"
    assert answers[0]["normalizedQuestion"] == "do you now or will you in the future require visa sponsorship"
    assert answers[0]["fieldType"] == "radio"
    assert answers[0]["answers"] == ["Yes"]
    assert answers[0]["sensitive"] is True


def test_form_answer_library_import_keeps_service_identity_and_newer_timestamps() -> None:
    with TestClient(create_app()) as client:
        create_response = client.post(
            "/api/v1/form-answer-library",
            json={
                "question": "Will you now or in the future require visa sponsorship?",
                "fieldType": "radio",
                "answers": ["Yes"],
                "sensitive": False,
            },
        )
        created = create_response.json()["answer"]
        import_response = client.post(
            "/api/v1/form-answer-library/import",
            json={
                "version": 1,
                "answers": [
                    {
                        "id": "legacy-older",
                        "question": "  Will you now or in the future require visa sponsorship? ",
                        "normalizedQuestion": "wrong-value",
                        "fieldType": "radio",
                        "answers": [" Yes "],
                        "sensitive": True,
                        "createdAt": "2026-07-01T00:00:00Z",
                        "updatedAt": "2026-07-02T00:00:00Z",
                        "lastUsedAt": "2026-07-03T00:00:00Z",
                    }
                ],
            },
        )
        read_response = client.get("/api/v1/form-answer-library")

    assert import_response.status_code == 200
    answer = read_response.json()["answers"][0]
    assert answer["id"] == created["id"]
    assert answer["createdAt"] == "2026-07-01T00:00:00Z"
    assert answer["updatedAt"] == created["updatedAt"]
    assert answer["lastUsedAt"] == created["lastUsedAt"]
    assert answer["sensitive"] is True


def test_form_answer_library_malformed_json_request_preserves_previous_valid_file() -> None:
    with TestClient(create_app()) as client:
        create_response = client.post(
            "/api/v1/form-answer-library",
            json={
                "question": "LinkedIn profile URL",
                "fieldType": "url",
                "answers": ["https://example.test/in/user"],
                "sensitive": False,
            },
        )
        library_path = _library_path()
        before = library_path.read_text(encoding="utf-8")
        malformed_response = client.post(
            "/api/v1/form-answer-library/import",
            content="{",
            headers={"Content-Type": "application/json"},
        )
        after = library_path.read_text(encoding="utf-8")

    assert create_response.status_code == 200
    assert malformed_response.status_code == 422
    assert before == after


def test_form_answer_library_clear_preserves_unrelated_private_config() -> None:
    ai_provider_path = _private_dir() / "ai-provider.json"
    ai_provider_path.parent.mkdir(parents=True, exist_ok=True)
    ai_provider_path.write_text(json.dumps({"provider": "openai", "api_key": "test-key"}), encoding="utf-8")
    ai_provider_before = ai_provider_path.read_text(encoding="utf-8")

    with TestClient(create_app()) as client:
        create_response = client.post(
            "/api/v1/form-answer-library",
            json={
                "question": "Portfolio website",
                "fieldType": "url",
                "answers": ["https://example.test"],
                "sensitive": False,
            },
        )
        clear_response = client.delete("/api/v1/form-answer-library")
        read_response = client.get("/api/v1/form-answer-library")

    assert create_response.status_code == 200
    assert clear_response.status_code == 200
    assert read_response.status_code == 200
    assert read_response.json()["answers"] == []
    assert not _library_path().exists()
    assert ai_provider_path.exists()
    assert ai_provider_path.read_text(encoding="utf-8") == ai_provider_before


def test_form_answer_library_validation_error_redacts_sensitive_input_values() -> None:
    secret = "TOP-SECRET-ANSWER-DO-NOT-ECHO"

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/v1/form-answer-library",
            json={
                "question": "Preferred work authorization note",
                "fieldType": "text",
                "answers": [secret, "   "],
                "sensitive": True,
            },
        )

    assert response.status_code == 422
    assert secret not in response.text
    assert "input" not in response.text


def test_form_answer_library_rejects_blank_import_fields_and_invalid_timestamps() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/v1/form-answer-library/import",
            json={
                "version": 1,
                "answers": [
                    {
                        "id": " ",
                        "question": "Visa sponsorship needed?",
                        "normalizedQuestion": " ",
                        "fieldType": "radio",
                        "answers": ["Yes"],
                        "sensitive": False,
                        "createdAt": "not-a-timestamp",
                        "updatedAt": "2026-07-05",
                        "lastUsedAt": "",
                    }
                ],
            },
        )

    assert response.status_code == 422
    assert "input" not in response.text


def test_form_answer_library_invalid_persisted_record_returns_500() -> None:
    library_path = _library_path()
    library_path.parent.mkdir(parents=True, exist_ok=True)
    library_path.write_text(
        json.dumps(
            {
                "version": 1,
                "answers": [
                    {
                        "id": "",
                        "question": "Saved question",
                        "normalizedQuestion": "saved question",
                        "fieldType": "text",
                        "answers": ["answer"],
                        "sensitive": False,
                        "createdAt": "2026-07-05T00:00:00Z",
                        "updatedAt": "2026-07-05T00:00:00Z",
                        "lastUsedAt": "2026-07-05T00:00:00Z",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with TestClient(create_app()) as client:
        response = client.get("/api/v1/form-answer-library")

    assert response.status_code == 500
    assert response.json()["detail"] == "Saved answers file is unreadable."


def _private_dir() -> Path:
    return Path(os.environ["LOCALAPPDATA"]) / "NxJob" / "private"


def _library_path() -> Path:
    return _private_dir() / "form-answer-library.v1.json"
