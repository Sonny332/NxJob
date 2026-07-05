from __future__ import annotations

import sqlite3
import json

from fastapi.testclient import TestClient
import pytest

from nxjob.core.workflow_cache import workflow_cache_key
from nxjob.data.dol_lca_history import INDEX_SCHEMA_VERSION, local_dol_lca_cache_fingerprint, normalize_employer_name
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


def test_sponsorship_role_not_eligible_wording_uses_hard_negative_rule(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))

    with TestClient(create_app()) as client:
        job_id = _capture_job(
            client,
            "Data Center Engineer. This role is not eligible for sponsorship now or in the future.",
        )
        response = client.post(
            "/api/v1/sponsorship/analyze",
            json={"job_lead_id": job_id, "allow_ai": True},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["sponsorship"]["status"] == "does_not_support"
    assert body["sponsorship"]["confidence"] >= 0.93
    assert body["ai_used"] is False


@pytest.mark.parametrize(
    "jd_text",
    [
        "No sponsorship is available for this role.",
        "The employer will not provide visa sponsorship.",
        "Applicants requiring future sponsorship cannot be considered.",
        "This position does not offer H-1B sponsorship.",
    ],
)
def test_sponsorship_hard_negative_wording_variants_use_local_rules(
    tmp_path, monkeypatch, jd_text: str
) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))

    with TestClient(create_app()) as client:
        job_id = _capture_job(client, jd_text)
        response = client.post(
            "/api/v1/sponsorship/analyze",
            json={"job_lead_id": job_id, "allow_ai": True},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["sponsorship"]["status"] == "does_not_support"
    assert body["sponsorship"]["confidence"] >= 0.9
    assert body["ai_used"] is False


def test_sponsorship_without_sponsorship_now_or_future_is_hard_negative(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))

    with TestClient(create_app()) as client:
        job_id = _capture_job(
            client,
            "Applicants must be authorized to work in the United States without sponsorship now or in the future.",
        )
        response = client.post(
            "/api/v1/sponsorship/analyze",
            json={"job_lead_id": job_id, "allow_ai": True},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["sponsorship"]["status"] == "does_not_support"
    assert body["sponsorship"]["confidence"] >= 0.9
    assert body["ai_used"] is False


def test_sponsorship_without_sponsorship_now_or_future_uses_local_rule_over_dol_history(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))
    monkeypatch.setattr(
        "nxjob.api.sponsorship.resolve_dol_lca_history",
        lambda company_name: _fake_dol_result(
            match_count=7,
            recent_certified_count=3,
            employer_name=company_name,
        ),
    )

    with TestClient(create_app()) as client:
        job_id = _capture_job(
            client,
            "Applicants must be authorized to work in the United States without sponsorship now or in the future.",
            company_name="Acme Data Inc",
        )
        response = client.post(
            "/api/v1/sponsorship/analyze",
            json={"job_lead_id": job_id, "allow_ai": True, "allow_public_lookup": True},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["sponsorship"]["status"] == "does_not_support"
    assert body["ai_used"] is False
    assert not any(item["source"] == "dol_lca_history" for item in body["evidence"])


def test_sponsorship_strong_dol_history_promotes_ambiguous_jd(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))

    class FakeDolResult:
        manifest_fingerprint = "dol-test-fingerprint"
        index_schema_version = 1
        warnings = []
        match_count = 7
        recent_certified_count = 3
        evidence = [
            {
                "employer_name": "Acme Data Inc",
                "job_title": "Software Engineer",
                "soc_code": "15-1252",
                "worksite": "Seattle, WA",
                "case_status": "Certified",
                "decision_date": "2026-02-15",
                "fy": 2026,
            }
        ]

    monkeypatch.setattr(
        "nxjob.api.sponsorship.resolve_dol_lca_history",
        lambda company_name: FakeDolResult(),
    )

    with TestClient(create_app()) as client:
        job_id = _capture_job(
            client,
            "Candidates must be authorized to work in the United States.",
            company_name="Acme Data Inc",
        )
        response = client.post(
            "/api/v1/sponsorship/analyze",
            json={"job_lead_id": job_id, "allow_ai": False, "allow_public_lookup": True},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["sponsorship"]["status"] == "likely_supports"
    assert body["sponsorship"]["confidence"] >= 0.7
    assert any(item["source"] == "dol_lca_history" for item in body["evidence"])
    assert "dol_lca_match_count=7" in body["sponsorship"]["summary"]


def test_sponsorship_dol_only_likely_supports_can_use_ai_review(
    tmp_path, monkeypatch
) -> None:
    _configure_ai_test_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "nxjob.api.sponsorship.resolve_dol_lca_history",
        lambda company_name: _fake_dol_result(
            match_count=7,
            recent_certified_count=3,
            employer_name=company_name,
        ),
    )

    def fake_urlopen(request, timeout):
        return _fake_ai_response(
            {
                "status": "needs_confirmation",
                "confidence": 0.61,
                "summary": "AI review still needs role-specific confirmation.",
                "evidence": "DOL history is company-level only.",
                "risk_flags": ["DOL history does not confirm this role."],
                "questions_to_confirm": ["Can the employer sponsor this role?"],
            }
        )

    monkeypatch.setattr("nxjob.ai.openai_compatible.urlopen", fake_urlopen)

    with TestClient(create_app()) as client:
        job_id = _capture_job(
            client,
            "Candidates must be authorized to work in the United States.",
            company_name="Acme Data Inc",
        )
        response = client.post(
            "/api/v1/sponsorship/analyze",
            json={"job_lead_id": job_id, "allow_ai": True, "allow_public_lookup": True},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["ai_used"] is True
    assert body["sponsorship"]["status"] == "needs_confirmation"
    assert any(item["source"] == "dol_lca_history" for item in body["evidence"])


def test_sponsorship_page_title_fallback_supplies_effective_dol_employer(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))
    resolver_calls: list[str] = []

    def fake_resolver(company_name: str):
        resolver_calls.append(company_name)
        return _fake_dol_result(
            match_count=7,
            recent_certified_count=3,
            employer_name=company_name,
        )

    monkeypatch.setattr("nxjob.api.sponsorship.resolve_dol_lca_history", fake_resolver)

    with TestClient(create_app()) as client:
        job_id = _capture_job(
            client,
            "Candidates must be authorized to work in the United States.",
            company_name="",
            page_title="Energy Analyst, Portfolio | Meta | LinkedIn",
        )
        response = client.post(
            "/api/v1/sponsorship/analyze",
            json={"job_lead_id": job_id, "allow_ai": False, "allow_public_lookup": True},
        )

    body = response.json()
    assert response.status_code == 200
    assert resolver_calls == ["Meta"]
    assert body["sponsorship"]["status"] == "likely_supports"
    assert any(item["source"] == "dol_lca_history" for item in body["evidence"])


def test_sponsorship_page_title_at_suffix_fallback_strips_job_board_suffix(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))
    resolver_calls: list[str] = []

    def fake_resolver(company_name: str):
        resolver_calls.append(company_name)
        return _fake_dol_result(
            match_count=7,
            recent_certified_count=3,
            employer_name=company_name,
        )

    monkeypatch.setattr("nxjob.api.sponsorship.resolve_dol_lca_history", fake_resolver)

    with TestClient(create_app()) as client:
        job_id = _capture_job(
            client,
            "Candidates must be authorized to work in the United States.",
            company_name="",
            page_title="Software Engineer at Meta | LinkedIn",
        )
        response = client.post(
            "/api/v1/sponsorship/analyze",
            json={"job_lead_id": job_id, "allow_ai": False, "allow_public_lookup": True},
        )

    body = response.json()
    assert response.status_code == 200
    assert resolver_calls == ["Meta"]
    assert body["sponsorship"]["status"] == "likely_supports"


def test_sponsorship_jd_header_fallback_supplies_effective_dol_employer(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))
    resolver_calls: list[str] = []

    def fake_resolver(company_name: str):
        resolver_calls.append(company_name)
        return _fake_dol_result(
            match_count=5,
            recent_certified_count=2,
            employer_name=company_name,
        )

    monkeypatch.setattr("nxjob.api.sponsorship.resolve_dol_lca_history", fake_resolver)

    with TestClient(create_app()) as client:
        job_id = _capture_job(
            client,
            "Meta\nEnergy Analyst, Portfolio\nSeattle, WA\nCandidates must be authorized to work in the United States.",
            company_name="",
            page_title="Sponsorship test",
        )
        response = client.post(
            "/api/v1/sponsorship/analyze",
            json={"job_lead_id": job_id, "allow_ai": False, "allow_public_lookup": True},
        )

    body = response.json()
    assert response.status_code == 200
    assert resolver_calls == ["Meta"]
    assert body["sponsorship"]["status"] == "likely_supports"


def test_sponsorship_jd_header_fallback_skips_job_title_before_company(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))
    resolver_calls: list[str] = []

    def fake_resolver(company_name: str):
        resolver_calls.append(company_name)
        return _fake_dol_result(
            match_count=5,
            recent_certified_count=2,
            employer_name=company_name,
        )

    monkeypatch.setattr("nxjob.api.sponsorship.resolve_dol_lca_history", fake_resolver)

    with TestClient(create_app()) as client:
        job_id = _capture_job(
            client,
            "Software Engineer\nMeta\nSeattle, WA\nCandidates must be authorized to work in the United States.",
            company_name="",
            page_title="Sponsorship test",
        )
        response = client.post(
            "/api/v1/sponsorship/analyze",
            json={"job_lead_id": job_id, "allow_ai": False, "allow_public_lookup": True},
        )

    body = response.json()
    assert response.status_code == 200
    assert resolver_calls == ["Meta"]
    assert body["sponsorship"]["status"] == "likely_supports"


def test_sponsorship_jd_explicit_rejection_overrides_dol_history(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))

    class FakeDolResult:
        manifest_fingerprint = "dol-test-fingerprint"
        index_schema_version = 1
        warnings = []
        match_count = 12
        recent_certified_count = 8
        evidence = [
            {
                "employer_name": "Acme Data Inc",
                "job_title": "Software Engineer",
                "soc_code": "15-1252",
                "worksite": "Seattle, WA",
                "case_status": "Certified",
                "decision_date": "2026-02-15",
                "fy": 2026,
            }
        ]

    monkeypatch.setattr(
        "nxjob.api.sponsorship.resolve_dol_lca_history",
        lambda company_name: FakeDolResult(),
    )

    with TestClient(create_app()) as client:
        job_id = _capture_job(
            client,
            "This role is not eligible for visa sponsorship.",
            company_name="Acme Data Inc",
        )
        response = client.post(
            "/api/v1/sponsorship/analyze",
            json={"job_lead_id": job_id, "allow_ai": False, "allow_public_lookup": True},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["sponsorship"]["status"] == "does_not_support"
    assert not any(item["source"] == "dol_lca_history" for item in body["evidence"])


def test_sponsorship_dol_cache_key_separates_same_jd_different_employers(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))

    def fake_resolver(company_name: str):
        if company_name == "Acme Data Inc":
            return _fake_dol_result(
                match_count=8,
                recent_certified_count=4,
                employer_name="Acme Data Inc",
            )
        return _fake_dol_result(
            match_count=0,
            recent_certified_count=0,
            employer_name=company_name,
        )

    monkeypatch.setattr("nxjob.api.sponsorship.resolve_dol_lca_history", fake_resolver)

    jd_text = "Candidates must be authorized to work in the United States."
    with TestClient(create_app()) as client:
        acme_job_id = _capture_job(client, jd_text, company_name="Acme Data Inc")
        beta_job_id = _capture_job(client, jd_text, company_name="Beta No History LLC")
        acme_response = client.post(
            "/api/v1/sponsorship/analyze",
            json={"job_lead_id": acme_job_id, "allow_ai": False, "allow_public_lookup": True},
        )
        beta_response = client.post(
            "/api/v1/sponsorship/analyze",
            json={"job_lead_id": beta_job_id, "allow_ai": False, "allow_public_lookup": True},
        )

    acme_body = acme_response.json()
    beta_body = beta_response.json()
    assert acme_response.status_code == 200
    assert beta_response.status_code == 200
    assert acme_body["sponsorship"]["status"] == "likely_supports"
    assert beta_body["cache"]["hit"] is False
    assert beta_body["sponsorship"]["status"] == "needs_confirmation"
    assert not any(item["source"] == "dol_lca_history" for item in beta_body["evidence"])


def test_sponsorship_dol_cache_key_uses_fallback_employer_for_same_jd(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))
    resolver_calls: list[str] = []

    def fake_resolver(company_name: str):
        resolver_calls.append(company_name)
        if company_name == "Meta":
            return _fake_dol_result(
                match_count=6,
                recent_certified_count=2,
                employer_name=company_name,
            )
        return _fake_dol_result(
            match_count=0,
            recent_certified_count=0,
            employer_name=company_name,
        )

    monkeypatch.setattr("nxjob.api.sponsorship.resolve_dol_lca_history", fake_resolver)

    jd_text = "Candidates must be authorized to work in the United States."
    with TestClient(create_app()) as client:
        meta_job_id = _capture_job(
            client,
            jd_text,
            company_name="",
            page_title="Energy Analyst, Portfolio | Meta | LinkedIn",
        )
        beta_job_id = _capture_job(
            client,
            jd_text,
            company_name="",
            page_title="Energy Analyst, Portfolio | Beta | LinkedIn",
        )
        meta_response = client.post(
            "/api/v1/sponsorship/analyze",
            json={"job_lead_id": meta_job_id, "allow_ai": False, "allow_public_lookup": True},
        )
        beta_response = client.post(
            "/api/v1/sponsorship/analyze",
            json={"job_lead_id": beta_job_id, "allow_ai": False, "allow_public_lookup": True},
        )

    meta_body = meta_response.json()
    beta_body = beta_response.json()
    assert meta_response.status_code == 200
    assert beta_response.status_code == 200
    assert resolver_calls == ["Meta", "Beta"]
    assert meta_body["sponsorship"]["status"] == "likely_supports"
    assert beta_body["cache"]["hit"] is False
    assert beta_body["sponsorship"]["status"] == "needs_confirmation"


def test_sponsorship_expired_dol_cache_network_failure_reuses_ai_workflow_cache(
    tmp_path, monkeypatch
) -> None:
    _configure_ai_test_env(tmp_path, monkeypatch)
    resolver_calls = 0
    ai_calls = 0

    def fake_resolver(company_name: str):
        nonlocal resolver_calls
        resolver_calls += 1
        return _fake_dol_result(
            match_count=0,
            recent_certified_count=0,
            employer_name="Acme Data Inc",
            warnings=["cache_expired_network_failed"],
        )

    def fake_urlopen(request, timeout):
        nonlocal ai_calls
        ai_calls += 1
        return _fake_ai_response(
            {
                "status": "needs_confirmation",
                "confidence": 0.61,
                "summary": "The JD is ambiguous and needs confirmation.",
                "evidence": "Candidates must be authorized to work in the United States.",
                "risk_flags": ["AI saw ambiguous work authorization wording."],
                "questions_to_confirm": ["Can the employer sponsor this role?"],
            }
        )

    monkeypatch.setattr("nxjob.api.sponsorship.resolve_dol_lca_history", fake_resolver)
    monkeypatch.setattr("nxjob.ai.openai_compatible.urlopen", fake_urlopen)

    with TestClient(create_app()) as client:
        job_id = _capture_job(
            client,
            "Candidates must be authorized to work in the United States.",
            company_name="Acme Data Inc",
        )
        first = client.post(
            "/api/v1/sponsorship/analyze",
            json={"job_lead_id": job_id, "allow_ai": True, "allow_public_lookup": True},
        )
        second = client.post(
            "/api/v1/sponsorship/analyze",
            json={"job_lead_id": job_id, "allow_ai": True, "allow_public_lookup": True},
        )

    first_body = first.json()
    second_body = second.json()
    assert first.status_code == 200
    assert second.status_code == 200
    assert first_body["cache"]["hit"] is False
    assert second_body["cache"]["hit"] is True
    assert second_body["trace_id"] == first_body["trace_id"]
    assert second_body["sponsorship"]["status"] == "needs_confirmation"
    assert resolver_calls == 1
    assert ai_calls == 1


def test_sponsorship_local_dol_cache_fingerprint_invalidates_workflow_cache(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))
    fingerprints = ["fingerprint-before-refresh", "fingerprint-after-refresh"]
    resolver_calls = 0

    def fake_fingerprint() -> str:
        return fingerprints.pop(0)

    def fake_resolver(company_name: str):
        nonlocal resolver_calls
        resolver_calls += 1
        if resolver_calls == 1:
            return _fake_dol_result(
                match_count=0,
                recent_certified_count=0,
                employer_name=company_name,
            )
        return _fake_dol_result(
            match_count=4,
            recent_certified_count=2,
            employer_name=company_name,
        )

    monkeypatch.setattr("nxjob.api.sponsorship.local_dol_lca_cache_fingerprint", fake_fingerprint)
    monkeypatch.setattr("nxjob.api.sponsorship.resolve_dol_lca_history", fake_resolver)

    with TestClient(create_app()) as client:
        job_id = _capture_job(
            client,
            "Candidates must be authorized to work in the United States.",
            company_name="Acme Data Inc",
        )
        first = client.post(
            "/api/v1/sponsorship/analyze",
            json={"job_lead_id": job_id, "allow_ai": False, "allow_public_lookup": True},
        )
        second = client.post(
            "/api/v1/sponsorship/analyze",
            json={"job_lead_id": job_id, "allow_ai": False, "allow_public_lookup": True},
        )

    first_body = first.json()
    second_body = second.json()
    assert first.status_code == 200
    assert second.status_code == 200
    assert first_body["cache"]["hit"] is False
    assert second_body["cache"]["hit"] is False
    assert first_body["sponsorship"]["status"] == "needs_confirmation"
    assert second_body["sponsorship"]["status"] == "likely_supports"
    assert resolver_calls == 2


def test_sponsorship_work_authorization_alone_remains_confirmation(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))

    with TestClient(create_app()) as client:
        job_id = _capture_job(
            client,
            "Candidates must be authorized to work in the United States. This employer participates in E-Verify.",
        )
        response = client.post(
            "/api/v1/sponsorship/analyze",
            json={"job_lead_id": job_id, "allow_ai": False},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["sponsorship"]["status"] == "needs_confirmation"
    assert 0.4 <= body["sponsorship"]["confidence"] <= 0.6
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


def _configure_ai_test_env(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))
    monkeypatch.setenv("NXJOB_AI_API_KEY", "test-api-key-secret")
    monkeypatch.setenv("NXJOB_AI_PROVIDER", "openai_compatible")
    monkeypatch.setenv("NXJOB_AI_BASE_URL", "https://api.example.test/v1")
    monkeypatch.setenv("NXJOB_AI_MODEL", "test-model")


def _fake_ai_response(payload: dict, *, total_tokens: int = 55) -> FakeAiResponse:
    return FakeAiResponse(
        {
            "model": "test-model",
            "usage": {"total_tokens": total_tokens},
            "choices": [
                {
                    "message": {
                        "content": json.dumps(payload),
                    }
                }
            ],
        }
    )


def test_sponsorship_ambiguous_text_reports_missing_ai_config(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))
    monkeypatch.delenv("NXJOB_AI_API_KEY", raising=False)

    with TestClient(create_app()) as client:
        job_id = _capture_job(
            client,
            "Candidates must be authorized to work in the United States. SECRET_JD_MARKER_DO_NOT_LOG.",
        )
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
    _configure_ai_test_env(tmp_path, monkeypatch)

    def fake_urlopen(request, timeout):
        request_body = json.loads(request.data.decode("utf-8"))
        assert request.get_header("Authorization") == "Bearer test-api-key-secret"
        assert request_body["model"] == "test-model"
        messages_text = json.dumps(request_body["messages"])
        assert "role-specific sponsorship policy" in messages_text
        assert "Generic work authorization language is not the same as no sponsorship" in messages_text
        assert "public/company-history evidence can only support likely_* statuses" in messages_text
        assert "hard screening wording like authorized to work without sponsorship now or in the future" in messages_text
        return _fake_ai_response(
            {
                "status": "needs_confirmation",
                "confidence": 0.72,
                "summary": "The JD requires work authorization but does not clearly confirm sponsorship support.",
                "evidence": "Candidates must be authorized to work in the United States.",
                "risk_flags": ["Work authorization language is ambiguous."],
                "questions_to_confirm": ["Can the employer sponsor this role?"],
            },
            total_tokens=123,
        )

    monkeypatch.setattr("nxjob.ai.openai_compatible.urlopen", fake_urlopen)

    with TestClient(create_app()) as client:
        job_id = _capture_job(
            client,
            "Candidates must be authorized to work in the United States. SECRET_JD_MARKER_DO_NOT_LOG.",
        )
        response = client.post(
            "/api/v1/sponsorship/analyze",
            json={"job_lead_id": job_id, "allow_ai": True},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["sponsorship"]["status"] == "needs_confirmation"
    assert body["ai_used"] is True
    assert "Work authorization language is ambiguous." in body["sponsorship"]["risk_flags"]
    assert "AI fallback is only a probability estimate, not a legal conclusion." in body["sponsorship"]["risk_flags"]
    assert any(item["source"] == "ai_inference" for item in body["evidence"])

    with sqlite3.connect(db_path) as connection:
        prompt_log = connection.execute(
            "SELECT input_summary, model, provider, error FROM prompt_logs WHERE workflow_name = ?",
            ("analyze_sponsorship",),
        ).fetchone()

    assert prompt_log == ("JD sponsorship indicators only; full JD not logged", "test-model", "openai", "")
    assert "test-api-key-secret" not in response.text
    assert "SECRET_JD_MARKER_DO_NOT_LOG" not in "\n".join(str(item) for item in prompt_log)


def test_sponsorship_missing_effective_employer_preserves_dol_missing_diagnostic(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))

    with TestClient(create_app()) as client:
        job_id = _capture_job(
            client,
            "Energy Analyst, Portfolio\nSeattle, WA\nCandidates must be authorized to work in the United States.",
            company_name="",
            page_title="Energy Analyst, Portfolio",
        )
        response = client.post(
            "/api/v1/sponsorship/analyze",
            json={"job_lead_id": job_id, "allow_ai": False, "allow_public_lookup": True},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["sponsorship"]["status"] == "needs_confirmation"
    assert "dol_lca_employer_name_missing" in body["sponsorship"]["risk_flags"]
    assert not any(item["source"] == "dol_lca_history" for item in body["evidence"])


def test_sponsorship_ai_fallback_preserves_dol_no_record_diagnostic(
    tmp_path, monkeypatch
) -> None:
    _configure_ai_test_env(tmp_path, monkeypatch)

    monkeypatch.setattr(
        "nxjob.api.sponsorship.resolve_dol_lca_history",
        lambda company_name: _fake_dol_result(
            match_count=0,
            recent_certified_count=0,
            employer_name=company_name,
        ),
    )

    def fake_urlopen(request, timeout):
        return _fake_ai_response(
            {
                "status": "needs_confirmation",
                "confidence": 0.61,
                "summary": "The JD is ambiguous and needs confirmation.",
                "evidence": "Candidates must be authorized to work in the United States.",
                "risk_flags": ["AI saw ambiguous work authorization wording."],
                "questions_to_confirm": ["Can the employer sponsor this role?"],
            }
        )

    monkeypatch.setattr("nxjob.ai.openai_compatible.urlopen", fake_urlopen)

    with TestClient(create_app()) as client:
        job_id = _capture_job(
            client,
            "Candidates must be authorized to work in the United States.",
            company_name="Meta",
            page_title="Energy Analyst, Portfolio | Meta | LinkedIn",
        )
        response = client.post(
            "/api/v1/sponsorship/analyze",
            json={"job_lead_id": job_id, "allow_ai": True, "allow_public_lookup": True},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["sponsorship"]["status"] == "needs_confirmation"
    assert body["ai_used"] is True
    assert (
        "DOL LCA history found no matching employer records; this does not prove non-support."
        in body["sponsorship"]["risk_flags"]
    )
    assert "AI saw ambiguous work authorization wording." in body["sponsorship"]["risk_flags"]
    assert not any(item["source"] == "dol_lca_history" for item in body["evidence"])


def test_sponsorship_dol_unavailable_does_not_claim_no_matching_records(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))
    monkeypatch.setattr(
        "nxjob.api.sponsorship.resolve_dol_lca_history",
        lambda company_name: _fake_dol_result(
            match_count=0,
            recent_certified_count=0,
            employer_name=company_name,
            warnings=["dol_lca_cache_refresh_required"],
        ),
    )

    with TestClient(create_app()) as client:
        job_id = _capture_job(
            client,
            "Candidates must be authorized to work in the United States.",
            company_name="Meta",
        )
        response = client.post(
            "/api/v1/sponsorship/analyze",
            json={"job_lead_id": job_id, "allow_ai": False, "allow_public_lookup": True},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["sponsorship"]["status"] == "needs_confirmation"
    assert "dol_lca_cache_refresh_required" in body["sponsorship"]["risk_flags"]
    assert (
        "DOL LCA history found no matching employer records; this does not prove non-support."
        not in body["sponsorship"]["risk_flags"]
    )


def test_sponsorship_ai_fallback_does_not_send_inferred_employer_as_company_name(
    tmp_path, monkeypatch
) -> None:
    _configure_ai_test_env(tmp_path, monkeypatch)

    resolver_calls: list[str] = []

    def fake_resolver(company_name: str):
        resolver_calls.append(company_name)
        return _fake_dol_result(
            match_count=0,
            recent_certified_count=0,
            employer_name=company_name,
        )

    monkeypatch.setattr("nxjob.api.sponsorship.resolve_dol_lca_history", fake_resolver)

    def fake_urlopen(request, timeout):
        request_body = json.loads(request.data.decode("utf-8"))
        user_payload = json.loads(request_body["messages"][1]["content"])
        assert user_payload["job"]["company_name"] == ""
        return _fake_ai_response(
            {
                "status": "needs_confirmation",
                "confidence": 0.61,
                "summary": "The JD is ambiguous and needs confirmation.",
                "evidence": "Candidates must be authorized to work in the United States.",
                "risk_flags": ["AI saw ambiguous work authorization wording."],
                "questions_to_confirm": ["Can the employer sponsor this role?"],
            }
        )

    monkeypatch.setattr("nxjob.ai.openai_compatible.urlopen", fake_urlopen)

    with TestClient(create_app()) as client:
        job_id = _capture_job(
            client,
            "Candidates must be authorized to work in the United States.",
            company_name="",
            page_title="Energy Analyst, Portfolio | Meta | LinkedIn",
        )
        response = client.post(
            "/api/v1/sponsorship/analyze",
            json={"job_lead_id": job_id, "allow_ai": True, "allow_public_lookup": True},
        )

    body = response.json()
    assert response.status_code == 200
    assert resolver_calls == ["Meta"]
    assert body["ai_used"] is True
    assert (
        "DOL LCA history found no matching employer records; this does not prove non-support."
        in body["sponsorship"]["risk_flags"]
    )


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


def test_sponsorship_cache_key_version_bump_avoids_v5_cache_entry(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "nxjob.sqlite3"
    monkeypatch.setenv("NXJOB_DB_PATH", str(db_path))

    with TestClient(create_app()) as client:
        job_id = _capture_job(
            client,
            "Software Engineer. Visa sponsorship is available for qualified candidates.",
            company_name="Acme Data Inc",
        )

        with sqlite3.connect(db_path) as connection:
            job_row = connection.execute(
                "SELECT jd_hash, company_name FROM job_leads WHERE id = ?",
                (job_id,),
            ).fetchone()
            assert job_row is not None
            jd_hash, company_name = job_row
            stale_cache_key = workflow_cache_key(
                "analyze_sponsorship",
                "v5",
                {
                    "jd_hash": jd_hash,
                    "application_form_text": "",
                    "allow_public_lookup": True,
                    "dol_effective_employer": normalize_employer_name(company_name),
                    "dol_index_schema_version": INDEX_SCHEMA_VERSION,
                    "dol_local_cache_fingerprint": local_dol_lca_cache_fingerprint(),
                    "allow_ai": False,
                    "ai_provider": "disabled",
                },
            )
            connection.execute(
                """
                INSERT INTO workflow_results (
                  id, job_lead_id, workflow_name, cache_key, created_at, trace_id,
                  status, result_summary, response_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "wfr_stale_v5",
                    job_id,
                    "analyze_sponsorship",
                    stale_cache_key,
                    "2026-01-01T00:00:00Z",
                    "trc_stale_v5",
                    "completed",
                    "stale cache entry",
                    json.dumps(
                        {
                            "trace_id": "trc_stale_v5",
                            "sponsorship": {
                                "status": "unknown",
                                "confidence": 0.1,
                                "summary": "stale cache entry",
                                "risk_flags": [],
                                "questions_to_confirm": [],
                                "is_legal_conclusion": False,
                            },
                            "evidence": [
                                {
                                    "source": "stale_cache",
                                    "evidence_text": "stale cache entry",
                                    "confidence": 0.1,
                                }
                            ],
                            "ai_used": False,
                            "cache": {"hit": True, "cache_key": stale_cache_key},
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
            connection.commit()

        response = client.post(
            "/api/v1/sponsorship/analyze",
            json={"job_lead_id": job_id, "allow_ai": False, "allow_public_lookup": True},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["cache"]["hit"] is False
    assert body["cache"]["cache_key"].startswith("analyze_sponsorship:v6:")
    assert body["cache"]["cache_key"] != stale_cache_key
    assert body["sponsorship"]["status"] == "supports"
    assert body["trace_id"] != "trc_stale_v5"


def _fake_dol_result(
    *,
    match_count: int,
    recent_certified_count: int,
    employer_name: str,
    warnings: list[str] | None = None,
):
    return type(
        "FakeDolResult",
        (),
        {
            "manifest_fingerprint": "dol-test-fingerprint",
            "index_schema_version": 1,
            "warnings": warnings or [],
            "match_count": match_count,
            "recent_certified_count": recent_certified_count,
            "evidence": [
                {
                    "employer_name": employer_name,
                    "job_title": "Software Engineer",
                    "soc_code": "15-1252",
                    "worksite": "Seattle, WA",
                    "case_status": "Certified",
                    "decision_date": "2026-02-15",
                    "fy": 2026,
                }
            ]
            if match_count
            else [],
        },
    )()


def _capture_job(
    client: TestClient,
    jd_text: str,
    company_name: str = "",
    page_title: str = "Sponsorship test",
) -> str:
    response = client.post(
        "/api/v1/job-leads/capture",
        json={
            "source_url": "https://example.com/jobs/sponsorship-test",
            "source_site": "company_ats",
            "page_title": page_title,
            "company_name": company_name,
            "selected_text": jd_text,
        },
    )
    assert response.status_code == 200
    return response.json()["job_lead"]["id"]
