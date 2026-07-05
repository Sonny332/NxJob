from __future__ import annotations

import json
import sqlite3
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from nxjob.data.dol_lca_history import DolDatasetFile, dol_manifest_fingerprint, normalize_employer_name
from nxjob.data.dol_lca_index_manager import (
    cleanup_dol_index_cache,
    get_dol_index_status,
    run_dol_index_build,
    verify_dol_index,
)
from nxjob.main import create_app


def test_index_status_reports_not_built_without_touching_network(tmp_path, monkeypatch) -> None:
    cache_dir = tmp_path / "dol-cache"
    monkeypatch.setenv("NXJOB_DOL_CACHE_DIR", str(cache_dir))
    monkeypatch.setenv("NXJOB_DOL_STATUS_CHECK_TTL_SECONDS", "86400")

    status = get_dol_index_status(check_remote=False)

    assert status.status == "not_built"
    assert status.cache_dir == str(cache_dir)
    assert status.active_index_ready is False
    assert "dol_lca_index_not_ready" in status.warnings


def test_build_downloads_streams_indexes_verifies_and_activates(tmp_path, monkeypatch) -> None:
    cache_dir = tmp_path / "dol-cache"
    monkeypatch.setenv("NXJOB_DOL_CACHE_DIR", str(cache_dir))
    monkeypatch.setenv("NXJOB_DOL_MAX_CACHE_BYTES", str(20 * 1024 * 1024))
    monkeypatch.setattr("nxjob.data.dol_lca_index_manager.urlopen", _fake_dol_urlopen)

    job = run_dol_index_build(force=True)

    assert job.status == "completed"
    assert job.phase == "completed"
    assert job.error == ""
    assert (cache_dir / "active.sqlite3").exists()
    assert (cache_dir / "manifest.json").exists()
    assert not any((cache_dir / "staging").glob("*"))

    manifest = json.loads((cache_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["row_count"] == 3
    assert manifest["index_schema_version"] == 1
    assert [item["fy"] for item in manifest["files"]] == [2026, 2025, 2024]

    verified = verify_dol_index()
    assert verified.status == "ready"
    assert verified.row_count == 3
    assert verified.active_index_ready is True


def test_refresh_required_status_marks_old_index_unusable(tmp_path, monkeypatch) -> None:
    cache_dir = tmp_path / "dol-cache"
    cache_dir.mkdir()
    index_path = cache_dir / "active.sqlite3"
    build_lca_index(
        [
            {
                "fy": 2026,
                "employer_name": "Acme Data Inc",
                "job_title": "Engineer",
                "soc_code": "15-1252",
                "worksite": "Austin, TX",
                "case_status": "Certified",
                "decision_date": datetime.now(UTC).date().isoformat(),
            }
        ],
        index_path,
    )
    stale_files = [
        DolDatasetFile(fy=2026, quarter=1, url="https://www.dol.gov/old/FY2026_Q1.xlsx"),
        DolDatasetFile(fy=2025, quarter=None, url="https://www.dol.gov/old/FY2025.xlsx"),
        DolDatasetFile(fy=2024, quarter=None, url="https://www.dol.gov/old/FY2024.xlsx"),
    ]
    _write_manifest(cache_dir, index_path, stale_files, checked_at=datetime.now(UTC))
    monkeypatch.setenv("NXJOB_DOL_CACHE_DIR", str(cache_dir))
    monkeypatch.setattr("nxjob.data.dol_lca_index_manager.urlopen", _fake_dol_urlopen)

    status = get_dol_index_status(check_remote=True)

    assert status.status == "refresh_required"
    assert status.active_index_ready is False
    assert "dol_lca_index_refresh_required" in status.warnings


def test_expired_index_is_not_ready(tmp_path, monkeypatch) -> None:
    cache_dir = tmp_path / "dol-cache"
    cache_dir.mkdir()
    index_path = cache_dir / "active.sqlite3"
    build_lca_index(
        [
            {
                "fy": 2026,
                "employer_name": "Acme Data Inc",
                "job_title": "Engineer",
                "soc_code": "15-1252",
                "worksite": "Austin, TX",
                "case_status": "Certified",
                "decision_date": datetime.now(UTC).date().isoformat(),
            }
        ],
        index_path,
    )
    files = [
        DolDatasetFile(fy=2026, quarter=2, url="https://www.dol.gov/files/LCA_Dislclosure_Data_FY2026_Q2.csv"),
        DolDatasetFile(fy=2025, quarter=None, url="https://www.dol.gov/files/LCA_Disclosure_Data_FY2025.csv"),
        DolDatasetFile(fy=2024, quarter=None, url="https://www.dol.gov/files/LCA_Disclosure_Data_FY2024.csv"),
    ]
    _write_manifest(cache_dir, index_path, files, checked_at=datetime.now(UTC) - timedelta(days=31))
    monkeypatch.setenv("NXJOB_DOL_CACHE_DIR", str(cache_dir))

    status = get_dol_index_status(check_remote=False)

    assert status.status == "expired"
    assert status.active_index_ready is False
    assert "dol_lca_index_expired" in status.warnings


def test_build_aborts_and_cleans_staging_when_cache_limit_is_exceeded(tmp_path, monkeypatch) -> None:
    cache_dir = tmp_path / "dol-cache"
    monkeypatch.setenv("NXJOB_DOL_CACHE_DIR", str(cache_dir))
    monkeypatch.setenv("NXJOB_DOL_MAX_CACHE_BYTES", "128")
    monkeypatch.setattr("nxjob.data.dol_lca_index_manager.urlopen", _fake_dol_urlopen)

    job = run_dol_index_build(force=True)

    assert job.status == "failed"
    assert "cache size limit" in job.error
    assert not (cache_dir / "active.sqlite3").exists()
    assert not any((cache_dir / "staging").glob("*"))


def test_cleanup_refuses_to_delete_active_without_confirmation(tmp_path, monkeypatch) -> None:
    cache_dir = tmp_path / "dol-cache"
    cache_dir.mkdir()
    active = cache_dir / "active.sqlite3"
    active.write_text("active", encoding="utf-8")
    stale = cache_dir / "index-old.tmp.sqlite3"
    stale.write_text("stale", encoding="utf-8")
    monkeypatch.setenv("NXJOB_DOL_CACHE_DIR", str(cache_dir))

    result = cleanup_dol_index_cache()

    assert active.exists()
    assert stale.name in result.deleted_files


def test_cleanup_removes_legacy_root_fy_downloads(tmp_path, monkeypatch) -> None:
    cache_dir = tmp_path / "dol-cache"
    downloads = cache_dir / "downloads"
    downloads.mkdir(parents=True)
    active = cache_dir / "active.sqlite3"
    active.write_text("active", encoding="utf-8")
    current_download = downloads / "FY2026-2-current.xlsx"
    current_download.write_text("current", encoding="utf-8")
    legacy_root_download = cache_dir / "FY2024-4-legacy.xlsx"
    legacy_root_download.write_text("legacy", encoding="utf-8")
    manifest = {
        "fingerprint": "test",
        "index_schema_version": 1,
        "checked_at": datetime.now(UTC).isoformat(),
        "active_index": str(active),
        "files": [
            {
                "fy": 2026,
                "quarter": 2,
                "url": "https://example.test/FY2026.xlsx",
                "path": str(current_download),
                "size_bytes": current_download.stat().st_size,
            }
        ],
    }
    (cache_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setenv("NXJOB_DOL_CACHE_DIR", str(cache_dir))

    result = cleanup_dol_index_cache()

    assert not legacy_root_download.exists()
    assert current_download.exists()
    assert active.exists()
    assert legacy_root_download.name in result.deleted_files


def test_cleanup_staging_match_only_applies_inside_cache_relative_path(tmp_path, monkeypatch) -> None:
    cache_parent = tmp_path / "staging-parent"
    cache_dir = cache_parent / "dol-cache"
    cache_dir.mkdir(parents=True)
    ordinary_file = cache_dir / "keep-me.txt"
    ordinary_file.write_text("keep", encoding="utf-8")
    manifest = {
        "fingerprint": "test",
        "index_schema_version": 1,
        "checked_at": datetime.now(UTC).isoformat(),
        "active_index": str(cache_dir / "active.sqlite3"),
        "files": [],
    }
    (cache_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setenv("NXJOB_DOL_CACHE_DIR", str(cache_dir))

    result = cleanup_dol_index_cache()

    assert ordinary_file.exists()
    assert ordinary_file.name not in result.deleted_files


def test_config_status_includes_dol_index_summary(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))
    monkeypatch.setenv("NXJOB_DOL_CACHE_DIR", str(tmp_path / "dol-cache"))

    with TestClient(create_app()) as client:
        response = client.get("/api/v1/config/status")

    assert response.status_code == 200
    body = response.json()
    assert body["dol_index_status"]["status"] == "not_built"
    assert body["dol_index_status"]["max_cache_bytes"] == 2 * 1024 * 1024 * 1024


def test_dol_index_api_starts_job_and_reports_status(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("NXJOB_DB_PATH", str(tmp_path / "nxjob.sqlite3"))
    monkeypatch.setenv("NXJOB_DOL_CACHE_DIR", str(tmp_path / "dol-cache"))
    monkeypatch.setattr("nxjob.data.dol_lca_index_manager.urlopen", _fake_dol_urlopen)

    with TestClient(create_app()) as client:
        started = client.post("/api/v1/dol/index/build", json={"force": True})
        job_id = started.json()["job_id"]
        job = None
        for _ in range(50):
            job = client.get(f"/api/v1/dol/index/jobs/{job_id}")
            if job.json()["phase"] == "completed":
                break
            time.sleep(0.1)
        status = client.get("/api/v1/dol/index/status")

    assert started.status_code == 200
    assert started.json()["status"] == "running"
    assert job is not None
    assert job.status_code == 200
    assert job.json()["phase"] == "completed"
    assert status.json()["status"] == "ready"


def _write_manifest(cache_dir: Path, index_path: Path, files: list[DolDatasetFile], checked_at: datetime) -> None:
    manifest = {
        "fingerprint": dol_manifest_fingerprint(files),
        "index_schema_version": 1,
        "checked_at": checked_at.isoformat(),
        "built_at": checked_at.isoformat(),
        "active_index": str(index_path),
        "row_count": _count_rows(index_path),
        "files": [{"fy": item.fy, "quarter": item.quarter, "url": item.url} for item in files],
    }
    (cache_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _count_rows(path: Path) -> int:
    with sqlite3.connect(path) as connection:
        return int(connection.execute("SELECT COUNT(*) FROM lca_cases").fetchone()[0])


def _fake_dol_urlopen(url, timeout=60):
    url = str(url)
    if "performance" in url:
        html = """
        <a href="/files/LCA_Dislclosure_Data_FY2026_Q2.csv">FY2026</a>
        <a href="/files/LCA_Disclosure_Data_FY2025.csv">FY2025</a>
        <a href="/files/LCA_Disclosure_Data_FY2024.csv">FY2024</a>
        """
        return FakeResponse(html.encode("utf-8"))
    if "FY2026" in url:
        return FakeResponse(_csv_bytes("Meta Platforms Inc", "Certified", "07/01/2026"))
    if "FY2025" in url:
        return FakeResponse(_csv_bytes("Acme Data Inc", "Certified", "02/01/2025"))
    if "FY2024" in url:
        return FakeResponse(_csv_bytes("Acme Data Inc", "Denied", "03/01/2024"))
    raise AssertionError(f"unexpected url: {url}")


def _csv_bytes(employer: str, status: str, decision_date: str) -> bytes:
    return (
        "EMPLOYER_NAME,JOB_TITLE,SOC_CODE,WORKSITE_CITY,WORKSITE_STATE,CASE_STATUS,DECISION_DATE\n"
        f"{employer},Software Engineer,15-1252,Austin,TX,{status},{decision_date}\n"
    ).encode("utf-8")


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.headers = {"Content-Length": str(len(payload))}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        if size == -1:
            data, self.payload = self.payload, b""
            return data
        data, self.payload = self.payload[:size], self.payload[size:]
        return data


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
