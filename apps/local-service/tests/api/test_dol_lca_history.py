from __future__ import annotations

import json
import os
import sqlite3
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from nxjob.data.dol_lca_history import (
    DolDatasetFile,
    discover_lca_dataset_files,
    dol_manifest_fingerprint,
    normalize_employer_name,
    resolve_dol_lca_history,
)
from nxjob.data.dol_lca_index_manager import get_dol_index_status, _iter_xlsx_rows_stream
from nxjob.main import create_app
from nxjob.settings.private_config import private_dol_cache_path


def test_config_status_reports_dol_cache_path_from_environment(tmp_path, monkeypatch) -> None:
    cache_dir = tmp_path / "dol cache"
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("NXJOB_DOL_CACHE_DIR", str(cache_dir))
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))

    with TestClient(create_app()) as client:
        response = client.get("/api/v1/config/status")

    body = response.json()
    assert response.status_code == 200
    assert body["dol_cache_dir_configured"] is True
    assert body["dol_cache_dir_source"] == "environment"
    assert body["dol_cache_dir"] == str(cache_dir)
    assert body["public_lookup_available"] is True


def test_config_can_save_manual_dol_cache_path(tmp_path, monkeypatch) -> None:
    cache_dir = tmp_path / "manual dol cache"
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    monkeypatch.delenv("NXJOB_DOL_CACHE_DIR", raising=False)
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/v1/config/dol-cache-directory",
            json={"path": str(cache_dir)},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["dol_cache_dir_configured"] is True
    assert body["dol_cache_dir_source"] == "private_config"
    assert body["dol_cache_dir"] == str(cache_dir)
    assert private_dol_cache_path().exists()


def test_discover_lca_dataset_files_selects_current_quarter_and_prior_full_years() -> None:
    html = """
    <a href="/sites/dolgov/files/ETA/oflc/pdfs/LCA_Dislclosure_Data_FY2026_Q1.xlsx">old</a>
    <a href="/sites/dolgov/files/ETA/oflc/pdfs/LCA_Dislclosure_Data_FY2026_Q2.xlsx">current</a>
    <a href="/sites/dolgov/files/ETA/oflc/pdfs/LCA_Disclosure_Data_FY2025.xlsx">full</a>
    <a href="/sites/dolgov/files/ETA/oflc/pdfs/LCA_Disclosure_Data_FY2024.xlsx">full</a>
    <a href="/sites/dolgov/files/ETA/oflc/pdfs/LCA_Disclosure_Data_FY2023.xlsx">too old</a>
    """

    files = discover_lca_dataset_files(html)

    assert [(item.fy, item.quarter) for item in files] == [(2026, 2), (2025, None), (2024, None)]
    assert files[0].url == "https://www.dol.gov/sites/dolgov/files/ETA/oflc/pdfs/LCA_Dislclosure_Data_FY2026_Q2.xlsx"


def test_resolver_uses_ready_non_expired_active_index_without_network(tmp_path, monkeypatch) -> None:
    cache_dir = tmp_path / "dol-cache"
    cache_dir.mkdir()
    index_path = cache_dir / "active.sqlite3"
    build_lca_index(
        [
            {
                "fy": 2026,
                "employer_name": "Acme Data Inc",
                "job_title": "Software Engineer",
                "soc_code": "15-1252",
                "worksite": "Seattle, WA",
                "case_status": "Certified",
                "decision_date": datetime.now(UTC).date().isoformat(),
            }
        ],
        index_path,
    )
    _write_manifest(cache_dir, index_path, checked_at=datetime.now(UTC))
    monkeypatch.setenv("NXJOB_DOL_CACHE_DIR", str(cache_dir))

    result = resolve_dol_lca_history("Acme Data Inc")

    assert result.match_count == 1
    assert result.recent_certified_count == 1
    assert result.warnings == []


def test_resolver_uses_manifest_active_index_path(tmp_path, monkeypatch) -> None:
    cache_dir = tmp_path / "dol-cache"
    cache_dir.mkdir()
    index_path = cache_dir / "custom-active.sqlite3"
    build_lca_index(
        [
            {
                "fy": 2026,
                "employer_name": "Acme Data Inc",
                "job_title": "Software Engineer",
                "soc_code": "15-1252",
                "worksite": "Seattle, WA",
                "case_status": "Certified",
                "decision_date": datetime.now(UTC).date().isoformat(),
            }
        ],
        index_path,
    )
    _write_manifest(cache_dir, index_path, checked_at=datetime.now(UTC))
    monkeypatch.setenv("NXJOB_DOL_CACHE_DIR", str(cache_dir))

    result = resolve_dol_lca_history("Acme Data Inc")

    assert result.match_count == 1
    assert result.recent_certified_count == 1
    assert result.warnings == []


def test_resolver_does_not_download_dataset_when_active_index_is_missing(
    tmp_path, monkeypatch
) -> None:
    cache_dir = tmp_path / "dol-cache"
    cache_dir.mkdir()
    monkeypatch.setenv("NXJOB_DOL_CACHE_DIR", str(cache_dir))

    result = resolve_dol_lca_history("Acme Data Inc")

    assert result.match_count == 0
    assert result.recent_certified_count == 0
    assert result.warnings == ["dol_lca_index_not_ready"]


def test_resolver_does_not_use_stale_index_when_manifest_url_changes(
    tmp_path, monkeypatch
) -> None:
    cache_dir = tmp_path / "dol-cache"
    cache_dir.mkdir()
    index_path = cache_dir / "active.sqlite3"
    build_lca_index(
        [
            {
                "fy": 2025,
                "employer_name": "Acme Data Inc",
                "job_title": "Software Engineer",
                "soc_code": "15-1252",
                "worksite": "Seattle, WA",
                "case_status": "Certified",
                "decision_date": datetime.now(UTC).date().isoformat(),
            }
        ],
        index_path,
    )
    stale_files = [
        DolDatasetFile(fy=2026, quarter=1, url="https://example.test/FY2026_Q1.xlsx"),
        DolDatasetFile(fy=2025, quarter=None, url="https://example.test/FY2025.xlsx"),
    ]
    _write_manifest(
        cache_dir,
        index_path,
        checked_at=datetime.now(UTC),
        fingerprint=dol_manifest_fingerprint(stale_files),
    )
    monkeypatch.setenv("NXJOB_DOL_CACHE_DIR", str(cache_dir))
    monkeypatch.setattr("nxjob.data.dol_lca_index_manager.urlopen", _performance_page_urlopen)

    status = get_dol_index_status(check_remote=True)
    result = resolve_dol_lca_history("Acme Data Inc")

    assert status.status == "refresh_required"
    assert result.match_count == 0
    assert result.recent_certified_count == 0
    assert result.warnings == ["dol_lca_index_refresh_required"]


def test_resolver_refuses_expired_cache_when_network_fails(tmp_path, monkeypatch) -> None:
    cache_dir = tmp_path / "dol-cache"
    cache_dir.mkdir()
    index_path = cache_dir / "active.sqlite3"
    build_lca_index(
        [
            {
                "fy": 2026,
                "employer_name": "Acme Data Inc",
                "job_title": "Software Engineer",
                "soc_code": "15-1252",
                "worksite": "Seattle, WA",
                "case_status": "Certified",
                "decision_date": datetime.now(UTC).date().isoformat(),
            }
        ],
        index_path,
    )
    _write_manifest(cache_dir, index_path, checked_at=datetime.now(UTC) - timedelta(days=31))
    monkeypatch.setenv("NXJOB_DOL_CACHE_DIR", str(cache_dir))

    result = resolve_dol_lca_history("Acme Data Inc")

    assert result.match_count == 0
    assert result.recent_certified_count == 0
    assert result.warnings == ["dol_lca_index_expired"]


def test_resolver_does_not_build_missing_index_inline(tmp_path, monkeypatch) -> None:
    cache_dir = tmp_path / "dol-cache"
    cache_dir.mkdir()
    html = """
    <a href="/sites/dolgov/files/ETA/oflc/pdfs/LCA_Dislclosure_Data_FY2026_Q2.xlsx">current</a>
    <a href="/sites/dolgov/files/ETA/oflc/pdfs/LCA_Disclosure_Data_FY2025.xlsx">full</a>
    <a href="/sites/dolgov/files/ETA/oflc/pdfs/LCA_Disclosure_Data_FY2024.xlsx">full</a>
    """
    monkeypatch.setenv("NXJOB_DOL_CACHE_DIR", str(cache_dir))
    monkeypatch.setattr("nxjob.data.dol_lca_index_manager.urlopen", lambda *args, **kwargs: FakeTextResponse(html))

    result = resolve_dol_lca_history("Acme Data Inc")

    assert result.match_count == 0
    assert result.recent_certified_count == 0
    assert result.warnings == ["dol_lca_index_not_ready"]
    assert not (cache_dir / "active.sqlite3").exists()


def test_resolver_does_not_rebuild_stale_index_inline(tmp_path, monkeypatch) -> None:
    cache_dir = tmp_path / "dol-cache"
    cache_dir.mkdir()
    index_path = cache_dir / "active.sqlite3"
    build_lca_index(
        [
            {
                "fy": 2025,
                "employer_name": "Acme Data Inc",
                "job_title": "Software Engineer",
                "soc_code": "15-1252",
                "worksite": "Seattle, WA",
                "case_status": "Certified",
                "decision_date": datetime.now(UTC).date().isoformat(),
            }
        ],
        index_path,
    )
    _write_manifest(cache_dir, index_path, checked_at=datetime.now(UTC))
    html = """
    <a href="/sites/dolgov/files/ETA/oflc/pdfs/LCA_Dislclosure_Data_FY2026_Q3.xlsx">new current</a>
    <a href="/sites/dolgov/files/ETA/oflc/pdfs/LCA_Disclosure_Data_FY2025.xlsx">full</a>
    <a href="/sites/dolgov/files/ETA/oflc/pdfs/LCA_Disclosure_Data_FY2024.xlsx">full</a>
    """
    monkeypatch.setenv("NXJOB_DOL_CACHE_DIR", str(cache_dir))
    monkeypatch.setattr("nxjob.data.dol_lca_index_manager.urlopen", lambda *args, **kwargs: FakeTextResponse(html))

    status = get_dol_index_status(check_remote=True)
    result = resolve_dol_lca_history("Acme Data Inc")

    assert status.status == "refresh_required"
    assert result.match_count == 0
    assert result.recent_certified_count == 0
    assert result.warnings == ["dol_lca_index_refresh_required"]


def test_resolver_counts_all_matches_and_recent_certified_beyond_display_limit(
    tmp_path, monkeypatch
) -> None:
    cache_dir = tmp_path / "dol-cache"
    cache_dir.mkdir()
    index_path = cache_dir / "active.sqlite3"
    today = datetime.now(UTC).date().isoformat()
    build_lca_index(
        [
            {
                "fy": 2026,
                "employer_name": "Acme Data Inc",
                "job_title": f"Software Engineer {index}",
                "soc_code": "15-1252",
                "worksite": "Seattle, WA",
                "case_status": "Certified",
                "decision_date": today,
            }
            for index in range(30)
        ],
        index_path,
    )
    _write_manifest(cache_dir, index_path, checked_at=datetime.now(UTC))
    monkeypatch.setenv("NXJOB_DOL_CACHE_DIR", str(cache_dir))

    result = resolve_dol_lca_history("Acme Data Inc")

    assert result.match_count == 30
    assert result.recent_certified_count == 30
    assert len(result.evidence) == 5


def test_resolver_matches_employer_full_name_prefixes_and_excel_serial_dates(tmp_path, monkeypatch) -> None:
    cache_dir = tmp_path / "dol-cache"
    cache_dir.mkdir()
    index_path = cache_dir / "active.sqlite3"
    build_lca_index(
        [
            {
                "fy": 2026,
                "employer_name": "Meta Platforms, Inc",
                "job_title": "Software Engineer",
                "soc_code": "15-1252",
                "worksite": "Menlo Park, CA",
                "case_status": "Certified",
                "decision_date": "46112",
            },
            {
                "fy": 2026,
                "employer_name": "Maven Clinic Co",
                "job_title": "Clinical Operations Manager",
                "soc_code": "11-9111",
                "worksite": "New York, NY",
                "case_status": "Certified",
                "decision_date": "45989",
            },
            {
                "fy": 2025,
                "employer_name": "Jacobs Engineering Group Inc",
                "job_title": "Mechanical Engineer",
                "soc_code": "17-2141",
                "worksite": "Harlan, IA",
                "case_status": "Certified",
                "decision_date": "45855",
            },
            {
                "fy": 2026,
                "employer_name": "Example Labs LLC",
                "job_title": "Research Engineer",
                "soc_code": "17-2199",
                "worksite": "Boston, MA",
                "case_status": "Certified",
                "decision_date": "46112.75",
            },
            {
                "fy": 2026,
                "employer_name": "Ryan Specialty LLC",
                "job_title": "Data Analyst",
                "soc_code": "15-2051",
                "worksite": "Chicago, IL",
                "case_status": "Certified",
                "decision_date": "46112",
            },
        ],
        index_path,
    )
    _write_manifest(cache_dir, index_path, checked_at=datetime.now(UTC))
    monkeypatch.setenv("NXJOB_DOL_CACHE_DIR", str(cache_dir))

    meta = resolve_dol_lca_history("Meta")
    maven = resolve_dol_lca_history("Maven Research")
    ryan = resolve_dol_lca_history("Ryan Companies US Inc")
    jacobs = resolve_dol_lca_history("Jacobs")
    example = resolve_dol_lca_history("Example Labs")

    assert meta.match_count == 1
    assert meta.recent_certified_count == 1
    assert meta.evidence[0]["decision_date"] == "2026-03-31"
    assert maven.match_count == 0
    assert maven.recent_certified_count == 0
    assert ryan.match_count == 0
    assert ryan.recent_certified_count == 0
    assert jacobs.match_count == 1
    assert jacobs.recent_certified_count == 1
    assert jacobs.evidence[0]["decision_date"] == "2025-07-17"
    assert example.match_count == 1
    assert example.recent_certified_count == 1
    assert example.evidence[0]["decision_date"] == "2026-03-31"


def test_resolver_closes_active_index_handle_after_query(tmp_path, monkeypatch) -> None:
    cache_dir = tmp_path / "dol-cache"
    cache_dir.mkdir()
    index_path = cache_dir / "active.sqlite3"
    replacement_path = cache_dir / "replacement.sqlite3"
    row = {
        "fy": 2026,
        "employer_name": "Acme Data Inc",
        "job_title": "Software Engineer",
        "soc_code": "15-1252",
        "worksite": "Seattle, WA",
        "case_status": "Certified",
        "decision_date": datetime.now(UTC).date().isoformat(),
    }
    build_lca_index([row], index_path)
    build_lca_index([row], replacement_path)
    _write_manifest(cache_dir, index_path, checked_at=datetime.now(UTC))
    monkeypatch.setenv("NXJOB_DOL_CACHE_DIR", str(cache_dir))

    result = resolve_dol_lca_history("Acme Data Inc")
    os.replace(replacement_path, index_path)
    index_path.unlink()

    assert result.match_count == 1
    assert not index_path.exists()


def test_sparse_xlsx_rows_preserve_omitted_blank_cells(tmp_path) -> None:
    workbook_path = tmp_path / "sparse-lca.xlsx"
    sheet_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
      <sheetData>
        <row r="1">
          <c r="A1" t="inlineStr"><is><t>EMPLOYER_NAME</t></is></c>
          <c r="B1" t="inlineStr"><is><t>JOB_TITLE</t></is></c>
          <c r="C1" t="inlineStr"><is><t>CASE_STATUS</t></is></c>
        </row>
        <row r="2">
          <c r="A2" t="inlineStr"><is><t>Acme Data Inc</t></is></c>
          <c r="C2" t="inlineStr"><is><t>Certified</t></is></c>
        </row>
      </sheetData>
    </worksheet>
    """
    with zipfile.ZipFile(workbook_path, "w") as archive:
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)

    rows = list(_iter_xlsx_rows_stream(workbook_path))

    assert rows == [
        {
            "employer_name": "Acme Data Inc",
            "job_title": "",
            "case_status": "Certified",
        }
    ]


def test_dol_manifest_fingerprint_changes_when_urls_change() -> None:
    first = [
        DolDatasetFile(fy=2026, quarter=2, url="https://example.test/fy2026q2.xlsx"),
        DolDatasetFile(fy=2025, quarter=None, url="https://example.test/fy2025.xlsx"),
    ]
    second = [
        DolDatasetFile(fy=2026, quarter=3, url="https://example.test/fy2026q3.xlsx"),
        DolDatasetFile(fy=2025, quarter=None, url="https://example.test/fy2025.xlsx"),
    ]

    assert dol_manifest_fingerprint(first) != dol_manifest_fingerprint(second)


def _write_manifest(
    cache_dir,
    index_path,
    checked_at: datetime,
    fingerprint: str = "test-fingerprint",
) -> None:
    manifest = {
        "fingerprint": fingerprint,
        "index_schema_version": 1,
        "checked_at": checked_at.isoformat(),
        "active_index": str(index_path),
        "files": [],
    }
    (cache_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def build_lca_index(rows: list[dict[str, object]], index_path: Path) -> None:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(index_path)
    try:
        connection.execute("DROP TABLE IF EXISTS lca_cases")
        connection.execute(
            """
            CREATE TABLE lca_cases (
              normalized_employer TEXT NOT NULL,
              fy INTEGER NOT NULL,
              employer_name TEXT NOT NULL,
              job_title TEXT NOT NULL,
              soc_code TEXT NOT NULL,
              worksite TEXT NOT NULL,
              case_status TEXT NOT NULL,
              decision_date TEXT NOT NULL
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO lca_cases (
              normalized_employer, fy, employer_name, job_title, soc_code,
              worksite, case_status, decision_date
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    normalize_employer_name(str(row.get("employer_name", ""))),
                    int(row.get("fy", 0) or 0),
                    str(row.get("employer_name", "")),
                    str(row.get("job_title", "")),
                    str(row.get("soc_code", "")),
                    str(row.get("worksite", "")),
                    str(row.get("case_status", "")),
                    str(row.get("decision_date", "")),
                )
                for row in rows
                if normalize_employer_name(str(row.get("employer_name", "")))
            ],
        )
        connection.execute("CREATE INDEX idx_lca_cases_employer ON lca_cases(normalized_employer)")
        connection.execute("CREATE INDEX idx_lca_cases_decision ON lca_cases(decision_date)")
        connection.commit()
    finally:
        connection.close()


def _performance_page_urlopen(*args, **kwargs):
    return FakeTextResponse()


class FakeTextResponse:
    def __init__(
        self,
        text: str = """
        <a href="/sites/dolgov/files/ETA/oflc/pdfs/LCA_Dislclosure_Data_FY2026_Q2.xlsx">current</a>
        <a href="/sites/dolgov/files/ETA/oflc/pdfs/LCA_Disclosure_Data_FY2025.xlsx">full</a>
        <a href="/sites/dolgov/files/ETA/oflc/pdfs/LCA_Disclosure_Data_FY2024.xlsx">full</a>
        """,
    ) -> None:
        self.text = text

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return self.text.encode("utf-8")
