from __future__ import annotations

import csv
import json
import os
import re
import shutil
import sqlite3
import uuid
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable
from urllib.request import urlopen
from xml.etree import ElementTree

from nxjob.data.dol_lca_history import (
    DEFAULT_TTL_DAYS,
    DOL_PERFORMANCE_URL,
    INDEX_SCHEMA_VERSION,
    DolDatasetFile,
    _parse_datetime,
    discover_lca_dataset_files,
    dol_manifest_fingerprint,
    normalize_employer_name,
)
from nxjob.settings.private_config import configured_dol_cache_dir, read_dol_max_cache_bytes

DEFAULT_STATUS_CHECK_TTL_SECONDS = 24 * 60 * 60
BATCH_SIZE = 5000
ACTIVE_INDEX_NAME = "active.sqlite3"
MANIFEST_NAME = "manifest.json"
STATE_NAME = "state.json"


@dataclass(frozen=True)
class DolIndexSelectedFile:
    fy: int
    quarter: int | None
    url: str
    path: str = ""
    size_bytes: int = 0


@dataclass(frozen=True)
class DolIndexJobRecord:
    job_id: str
    status: str
    phase: str
    message: str = ""
    error: str = ""
    started_at: str = ""
    completed_at: str = ""
    progress_current: int = 0
    progress_total: int = 0


@dataclass(frozen=True)
class DolIndexStatusRecord:
    status: str
    cache_dir: str
    active_index_ready: bool
    fingerprint: str = "unavailable"
    index_schema_version: int = INDEX_SCHEMA_VERSION
    last_built_at: str = ""
    last_checked_at: str = ""
    expires_at: str = ""
    row_count: int = 0
    cache_size_bytes: int = 0
    max_cache_bytes: int = 2 * 1024 * 1024 * 1024
    selected_files: list[DolIndexSelectedFile] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    current_job: DolIndexJobRecord | None = None


@dataclass(frozen=True)
class DolIndexCleanupRecord:
    deleted_files: list[str]
    freed_bytes: int
    warnings: list[str] = field(default_factory=list)


_JOBS: dict[str, DolIndexJobRecord] = {}


def get_dol_index_status(*, check_remote: bool = False, force_remote: bool = False) -> DolIndexStatusRecord:
    cache_dir = configured_dol_cache_dir()
    max_bytes = read_dol_max_cache_bytes()
    manifest = _read_json(cache_dir / MANIFEST_NAME)
    state = _read_json(cache_dir / STATE_NAME)
    active_index = Path(str(manifest.get("active_index") or cache_dir / ACTIVE_INDEX_NAME))
    cache_size = _directory_size(cache_dir)
    current_job = _current_running_job()

    if current_job is not None:
        return _status_from_manifest(
            cache_dir,
            manifest,
            active_index,
            "building",
            ["dol_lca_index_building"],
            cache_size,
            max_bytes,
            current_job,
        )

    if check_remote and _should_check_remote(state, force_remote):
        try:
            files = _discover_remote_files()
            fingerprint = dol_manifest_fingerprint(files)
            state = {
                **state,
                "last_remote_checked_at": datetime.now(UTC).isoformat(),
                "last_remote_fingerprint": fingerprint,
                "last_remote_files": [{"fy": item.fy, "quarter": item.quarter, "url": item.url} for item in files],
            }
            if manifest and manifest.get("fingerprint") != fingerprint:
                state["remote_status"] = "refresh_required"
            else:
                state["remote_status"] = "current"
            _write_json_atomic(cache_dir / STATE_NAME, state)
        except Exception as exc:
            state = {
                **state,
                "last_remote_checked_at": datetime.now(UTC).isoformat(),
                "last_remote_error": str(exc),
            }
            _write_json_atomic(cache_dir / STATE_NAME, state)

    if not manifest or not active_index.exists():
        return DolIndexStatusRecord(
            status="not_built",
            cache_dir=str(cache_dir),
            active_index_ready=False,
            cache_size_bytes=cache_size,
            max_cache_bytes=max_bytes,
            warnings=["dol_lca_index_not_ready"],
            current_job=current_job,
        )

    if state.get("remote_status") == "refresh_required":
        return _status_from_manifest(
            cache_dir,
            manifest,
            active_index,
            "refresh_required",
            ["dol_lca_index_refresh_required"],
            cache_size,
            max_bytes,
            current_job,
        )

    checked_at = _parse_datetime(str(manifest.get("checked_at", "")))
    if checked_at is None or datetime.now(UTC) - checked_at > timedelta(days=DEFAULT_TTL_DAYS):
        return _status_from_manifest(
            cache_dir,
            manifest,
            active_index,
            "expired",
            ["dol_lca_index_expired"],
            cache_size,
            max_bytes,
            current_job,
        )

    verified = _verify_index_file(active_index)
    if verified[0] is False:
        return _status_from_manifest(
            cache_dir,
            manifest,
            active_index,
            "failed_verification",
            ["dol_lca_index_failed_verification", verified[1]],
            cache_size,
            max_bytes,
            current_job,
        )

    return _status_from_manifest(cache_dir, manifest, active_index, "ready", [], cache_size, max_bytes, current_job)


def run_dol_index_build(*, force: bool = False, job_id: str | None = None) -> DolIndexJobRecord:
    cache_dir = configured_dol_cache_dir()
    job = _job(job_id or uuid.uuid4().hex, "running", "discovering", "Discovering DOL LCA disclosure files")
    _JOBS[job.job_id] = job
    staging_dir = cache_dir / "staging" / job.job_id
    try:
        _ensure_cache_layout(cache_dir)
        _remove_path(staging_dir)
        staging_dir.mkdir(parents=True, exist_ok=True)

        files = _discover_remote_files()
        if not files:
            raise RuntimeError("No DOL LCA disclosure files were discovered.")
        fingerprint = dol_manifest_fingerprint(files)
        active_status = get_dol_index_status(check_remote=False)
        if not force and active_status.status == "ready" and active_status.fingerprint == fingerprint:
            completed = _job(job.job_id, "completed", "completed", "DOL index is already current", started_at=job.started_at)
            _JOBS[job.job_id] = completed
            return completed

        downloaded: list[tuple[DolDatasetFile, Path]] = []
        for index, file in enumerate(files, start=1):
            _set_job(job.job_id, "running", "downloading", f"Downloading FY{file.fy}", index - 1, len(files))
            downloaded.append((file, _download_dataset_stream(cache_dir, staging_dir, file)))

        _set_job(job.job_id, "running", "indexing", "Building sqlite index", 0, len(downloaded))
        staging_index = staging_dir / ACTIVE_INDEX_NAME
        row_count = build_lca_index_from_files(downloaded, staging_index)

        _set_job(job.job_id, "running", "verifying", "Verifying sqlite index", len(downloaded), len(downloaded))
        verified, detail = _verify_index_file(staging_index)
        if not verified:
            raise RuntimeError(detail or "DOL index verification failed.")
        if row_count <= 0:
            raise RuntimeError("DOL index contains no rows.")

        _enforce_cache_limit(cache_dir, extra_paths=[staging_index])
        _set_job(job.job_id, "running", "activating", "Activating DOL index", 0, 0)
        downloads_dir = cache_dir / "downloads"
        downloads_dir.mkdir(parents=True, exist_ok=True)
        active_files: list[DolIndexSelectedFile] = []
        for file, staged_path in downloaded:
            final_path = downloads_dir / staged_path.name
            os.replace(staged_path, final_path)
            active_files.append(
                DolIndexSelectedFile(
                    fy=file.fy,
                    quarter=file.quarter,
                    url=file.url,
                    path=str(final_path),
                    size_bytes=final_path.stat().st_size,
                )
            )

        active_index = cache_dir / ACTIVE_INDEX_NAME
        os.replace(staging_index, active_index)
        now = datetime.now(UTC)
        _write_json_atomic(
            cache_dir / MANIFEST_NAME,
            {
                "fingerprint": fingerprint,
                "index_schema_version": INDEX_SCHEMA_VERSION,
                "checked_at": now.isoformat(),
                "built_at": now.isoformat(),
                "expires_at": (now + timedelta(days=DEFAULT_TTL_DAYS)).isoformat(),
                "active_index": str(active_index),
                "row_count": row_count,
                "files": [asdict(item) for item in active_files],
            },
        )
        _write_json_atomic(
            cache_dir / STATE_NAME,
            {
                "last_remote_checked_at": now.isoformat(),
                "last_remote_fingerprint": fingerprint,
                "remote_status": "current",
            },
        )

        _set_job(job.job_id, "running", "cleaning", "Cleaning stale DOL cache files", 0, 0)
        cleanup_dol_index_cache()
        completed = _job(job.job_id, "completed", "completed", "DOL index build completed", started_at=job.started_at)
        _JOBS[job.job_id] = completed
        return completed
    except Exception as exc:
        try:
            _remove_path(staging_dir)
        except OSError:
            pass
        failed = _job(job.job_id, "failed", "failed", "DOL index build failed", str(exc), started_at=job.started_at)
        _JOBS[job.job_id] = failed
        return failed


def start_dol_index_build(*, force: bool = False) -> DolIndexJobRecord:
    running = _current_running_job()
    if running is not None:
        return running

    import threading

    job_id = uuid.uuid4().hex
    job = _job(job_id, "running", "queued", "DOL index build queued")
    _JOBS[job_id] = job
    thread = threading.Thread(target=run_dol_index_build, kwargs={"force": force, "job_id": job_id}, daemon=True)
    thread.start()
    return job


def get_dol_index_job(job_id: str) -> DolIndexJobRecord | None:
    return _JOBS.get(job_id)


def verify_dol_index() -> DolIndexStatusRecord:
    return get_dol_index_status(check_remote=False)


def cleanup_dol_index_cache() -> DolIndexCleanupRecord:
    cache_dir = configured_dol_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    manifest = _read_json(cache_dir / MANIFEST_NAME)
    keep_paths = {cache_dir / MANIFEST_NAME, cache_dir / STATE_NAME}
    active_index = Path(str(manifest.get("active_index") or cache_dir / ACTIVE_INDEX_NAME))
    keep_paths.add(active_index)
    for file in manifest.get("files", []):
        path = Path(str(file.get("path", "")))
        if path:
            keep_paths.add(path)

    deleted: list[str] = []
    freed = 0
    warnings: list[str] = []
    for path in list(cache_dir.rglob("*")):
        if path.is_dir():
            continue
        if not _is_within(path, cache_dir):
            warnings.append(f"skip_outside_cache:{path}")
            continue
        relative_parts = path.relative_to(cache_dir).parts
        if path in keep_paths:
            continue
        if (
            path.name.endswith(".tmp")
            or "staging" in relative_parts
            or path.parent.name == "downloads"
            or path.name.startswith("index-")
            or _is_legacy_root_dataset(path, cache_dir)
        ):
            size = path.stat().st_size
            path.unlink(missing_ok=True)
            deleted.append(path.name)
            freed += size

    staging_dir = cache_dir / "staging"
    if staging_dir.exists():
        for child in staging_dir.iterdir():
            if child.is_dir():
                _remove_path(child)
    return DolIndexCleanupRecord(deleted_files=deleted, freed_bytes=freed, warnings=warnings)


def active_dol_index_fingerprint() -> str:
    status = get_dol_index_status(check_remote=False)
    return status.fingerprint if status.status == "ready" else "unavailable"


def build_lca_index_from_files(files: list[tuple[DolDatasetFile, Path]], index_path: Path) -> int:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    row_count = 0
    connection = sqlite3.connect(index_path)
    try:
        _initialize_index(connection)
        batch: list[tuple[str, int, str, str, str, str, str, str]] = []
        for file, path in files:
            for row in _iter_lca_rows(path, file.fy):
                normalized = normalize_employer_name(str(row.get("employer_name", "")))
                if not normalized:
                    continue
                batch.append(
                    (
                        normalized,
                        int(row.get("fy", 0) or 0),
                        str(row.get("employer_name", "")),
                        str(row.get("job_title", "")),
                        str(row.get("soc_code", "")),
                        str(row.get("worksite", "")),
                        str(row.get("case_status", "")),
                        str(row.get("decision_date", "")),
                    )
                )
                if len(batch) >= BATCH_SIZE:
                    row_count += _insert_batch(connection, batch)
                    batch = []
        if batch:
            row_count += _insert_batch(connection, batch)
        connection.execute("CREATE INDEX idx_lca_cases_employer ON lca_cases(normalized_employer)")
        connection.execute("CREATE INDEX idx_lca_cases_decision ON lca_cases(decision_date)")
        connection.commit()
    finally:
        connection.close()
    return row_count


def _row_from_source(row: dict[str, Any], fy: int) -> dict[str, Any]:
    normalized = {_normalize_header(key): value for key, value in row.items()}
    city = _pick(normalized, "worksite_city", "worksite_1_city", "place_of_employment_city")
    state = _pick(normalized, "worksite_state", "worksite_1_state", "place_of_employment_state")
    return {
        "fy": fy,
        "employer_name": _pick(normalized, "employer_name", "employer_legal_business_name"),
        "job_title": _pick(normalized, "job_title", "job_title_text"),
        "soc_code": _pick(normalized, "soc_code", "soc_code_1"),
        "worksite": ", ".join(part for part in [city, state] if part),
        "case_status": _pick(normalized, "case_status", "case_status_name"),
        "decision_date": _pick(normalized, "decision_date", "case_status_date", "determination_date"),
    }


def _iter_lca_rows(path: Path, fy: int) -> Iterable[dict[str, Any]]:
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                yield _row_from_source(row, fy)
        return
    for row in _iter_xlsx_rows_stream(path):
        yield _row_from_source(row, fy)


def _iter_xlsx_rows_stream(path: Path) -> Iterable[dict[str, str]]:
    shared_strings = _xlsx_shared_strings(path)
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        sheet_name = next(
            name for name in archive.namelist() if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
        )
        with archive.open(sheet_name) as sheet:
            headers: list[str] | None = None
            for _event, row in ElementTree.iterparse(sheet, events=("end",)):
                if not row.tag.endswith("row"):
                    continue
                values = _xlsx_row_values(row, shared_strings, namespace)
                row.clear()
                if not values:
                    continue
                if headers is None:
                    headers = [_normalize_header(value) for value in values]
                    continue
                yield {header: values[index] if index < len(values) else "" for index, header in enumerate(headers) if header}


def _xlsx_row_values(row: ElementTree.Element, shared_strings: list[str], namespace: dict[str, str]) -> list[str]:
    positioned_values: dict[int, str] = {}
    fallback_index = 0
    for cell in row.findall("x:c", namespace):
        column_index = _xlsx_cell_column_index(cell.attrib.get("r", ""))
        if column_index is None:
            column_index = fallback_index
        positioned_values[column_index] = _xlsx_cell_value(cell, shared_strings, namespace)
        fallback_index = column_index + 1
    if not positioned_values:
        return []
    values = [""] * (max(positioned_values) + 1)
    for column_index, value in positioned_values.items():
        values[column_index] = value
    return values


def _xlsx_shared_strings(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        if "xl/sharedStrings.xml" not in archive.namelist():
            return []
        root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    return ["".join(text.itertext()) for text in root.findall("x:si", namespace)]


def _xlsx_cell_value(cell: ElementTree.Element, shared_strings: list[str], namespace: dict[str, str]) -> str:
    cell_type = cell.attrib.get("t", "")
    value = cell.find("x:v", namespace)
    if value is None:
        inline = cell.find("x:is", namespace)
        return "".join(inline.itertext()) if inline is not None else ""
    raw = value.text or ""
    if cell_type == "s":
        try:
            return shared_strings[int(raw)]
        except (ValueError, IndexError):
            return ""
    return raw


def _xlsx_cell_column_index(reference: str) -> int | None:
    match = re.match(r"([A-Z]+)", reference.upper())
    if not match:
        return None
    column = 0
    for char in match.group(1):
        column = column * 26 + (ord(char) - ord("A") + 1)
    return column - 1


def _normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def _pick(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = str(row.get(key, "")).strip()
        if value:
            return value
    return ""


def _discover_remote_files() -> list[DolDatasetFile]:
    with urlopen(DOL_PERFORMANCE_URL, timeout=5) as response:
        html = response.read().decode("utf-8", errors="replace")
    return discover_lca_dataset_files(html)


def _download_dataset_stream(cache_dir: Path, staging_dir: Path, file: DolDatasetFile) -> Path:
    from hashlib import sha256

    digest = sha256(file.url.encode("utf-8")).hexdigest()[:16]
    suffix = Path(file.url).suffix or ".xlsx"
    final_name = f"FY{file.fy}-{file.quarter or 'full'}-{digest}{suffix}"
    existing = cache_dir / "downloads" / final_name
    if existing.exists():
        staged_existing = staging_dir / final_name
        shutil.copy2(existing, staged_existing)
        return staged_existing

    target = staging_dir / final_name
    temp_path = target.with_suffix(target.suffix + ".tmp")
    with urlopen(file.url, timeout=60) as response:
        content_length = int(response.headers.get("Content-Length", "0") or 0)
        if content_length:
            _enforce_cache_limit(cache_dir, incoming_bytes=content_length)
        with temp_path.open("wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                _enforce_cache_limit(cache_dir, extra_paths=[temp_path])
    os.replace(temp_path, target)
    return target


def _initialize_index(connection: sqlite3.Connection) -> None:
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


def _insert_batch(connection: sqlite3.Connection, batch: list[tuple[str, int, str, str, str, str, str, str]]) -> int:
    connection.executemany(
        """
        INSERT INTO lca_cases (
          normalized_employer, fy, employer_name, job_title, soc_code,
          worksite, case_status, decision_date
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        batch,
    )
    return len(batch)


def _verify_index_file(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "active index missing"
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(path)
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }
        if "lca_cases" not in tables:
            return False, "lca_cases table missing"
        row_count = int(connection.execute("SELECT COUNT(*) FROM lca_cases").fetchone()[0])
        if row_count <= 0:
            return False, "lca_cases has no rows"
        indexes = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'index'").fetchall()
        }
        if "idx_lca_cases_employer" not in indexes:
            return False, "employer index missing"
    except sqlite3.Error as exc:
        return False, str(exc)
    finally:
        if connection is not None:
            connection.close()
    return True, ""


def _status_from_manifest(
    cache_dir: Path,
    manifest: dict[str, Any],
    active_index: Path,
    status: str,
    warnings: list[str],
    cache_size: int,
    max_bytes: int,
    current_job: DolIndexJobRecord | None,
) -> DolIndexStatusRecord:
    files = [
        DolIndexSelectedFile(
            fy=int(item.get("fy", 0) or 0),
            quarter=item.get("quarter"),
            url=str(item.get("url", "")),
            path=str(item.get("path", "")),
            size_bytes=int(item.get("size_bytes", 0) or 0),
        )
        for item in manifest.get("files", [])
        if isinstance(item, dict)
    ]
    return DolIndexStatusRecord(
        status=status,
        cache_dir=str(cache_dir),
        active_index_ready=status == "ready" and active_index.exists(),
        fingerprint=str(manifest.get("fingerprint") or "unavailable"),
        index_schema_version=int(manifest.get("index_schema_version", INDEX_SCHEMA_VERSION) or INDEX_SCHEMA_VERSION),
        last_built_at=str(manifest.get("built_at", "")),
        last_checked_at=str(manifest.get("checked_at", "")),
        expires_at=str(manifest.get("expires_at", "")),
        row_count=int(manifest.get("row_count", 0) or 0),
        cache_size_bytes=cache_size,
        max_cache_bytes=max_bytes,
        selected_files=files,
        warnings=warnings,
        current_job=current_job,
    )


def _ensure_cache_layout(cache_dir: Path) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "downloads").mkdir(exist_ok=True)
    (cache_dir / "staging").mkdir(exist_ok=True)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp_path, path)


def _directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _enforce_cache_limit(cache_dir: Path, *, incoming_bytes: int = 0, extra_paths: list[Path] | None = None) -> None:
    max_bytes = read_dol_max_cache_bytes()
    extra = sum(
        path.stat().st_size
        for path in extra_paths or []
        if path.exists() and not _is_within(path, cache_dir)
    )
    total = _directory_size(cache_dir) + incoming_bytes + extra
    if total > max_bytes:
        raise RuntimeError(f"DOL cache size limit exceeded: {total} > {max_bytes}")


def _should_check_remote(state: dict[str, Any], force_remote: bool) -> bool:
    if force_remote:
        return True
    ttl = int(os.environ.get("NXJOB_DOL_STATUS_CHECK_TTL_SECONDS", str(DEFAULT_STATUS_CHECK_TTL_SECONDS)))
    checked_at = _parse_datetime(str(state.get("last_remote_checked_at", "")))
    return checked_at is None or datetime.now(UTC) - checked_at > timedelta(seconds=ttl)


def _current_running_job() -> DolIndexJobRecord | None:
    for job in _JOBS.values():
        if job.status == "running":
            return job
    return None


def _job(
    job_id: str,
    status: str,
    phase: str,
    message: str,
    error: str = "",
    *,
    started_at: str = "",
    progress_current: int = 0,
    progress_total: int = 0,
) -> DolIndexJobRecord:
    now = datetime.now(UTC).isoformat()
    return DolIndexJobRecord(
        job_id=job_id,
        status=status,
        phase=phase,
        message=message,
        error=error,
        started_at=started_at or now,
        completed_at=now if status in {"completed", "failed", "cancelled"} else "",
        progress_current=progress_current,
        progress_total=progress_total,
    )


def _set_job(job_id: str, status: str, phase: str, message: str, progress_current: int, progress_total: int) -> None:
    existing = _JOBS[job_id]
    _JOBS[job_id] = _job(
        job_id,
        status,
        phase,
        message,
        started_at=existing.started_at,
        progress_current=progress_current,
        progress_total=progress_total,
    )


def _remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def _is_legacy_root_dataset(path: Path, cache_dir: Path) -> bool:
    return path.parent == cache_dir and re.match(r"FY20\d{2}-.+\.(csv|xlsx)$", path.name, flags=re.IGNORECASE) is not None


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True
