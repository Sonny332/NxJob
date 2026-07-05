from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from nxjob.settings.private_config import configured_dol_cache_dir

DOL_PERFORMANCE_URL = "https://www.dol.gov/agencies/eta/foreign-labor/performance"
DOL_BASE_URL = "https://www.dol.gov"
INDEX_SCHEMA_VERSION = 1
DEFAULT_TTL_DAYS = 30
_CORPORATE_SUFFIX_TOKENS = {"INC", "LLC", "CORP", "CORPORATION", "COMPANY", "CO", "LTD", "PLC"}


@dataclass(frozen=True)
class DolDatasetFile:
    fy: int
    quarter: int | None
    url: str


@dataclass(frozen=True)
class DolHistoryResult:
    manifest_fingerprint: str = "unavailable"
    index_schema_version: int = INDEX_SCHEMA_VERSION
    warnings: list[str] = field(default_factory=list)
    match_count: int = 0
    recent_certified_count: int = 0
    evidence: list[dict[str, Any]] = field(default_factory=list)


def resolve_dol_lca_history(employer_name: str) -> DolHistoryResult:
    normalized = normalize_employer_name(employer_name)
    if not normalized:
        return DolHistoryResult(warnings=["dol_lca_employer_name_missing"])

    from nxjob.data.dol_lca_index_manager import get_dol_index_status

    cache_dir = configured_dol_cache_dir()
    status = get_dol_index_status(check_remote=False)
    if status.status != "ready":
        return DolHistoryResult(
            manifest_fingerprint=status.fingerprint,
            warnings=status.warnings or ["dol_lca_index_not_ready"],
        )

    return _query_history(
        _active_index_path_from_manifest(cache_dir),
        normalized,
        status.fingerprint,
        [],
    )


def local_dol_lca_cache_fingerprint() -> str:
    from nxjob.data.dol_lca_index_manager import active_dol_index_fingerprint

    return active_dol_index_fingerprint()


def discover_lca_dataset_files(html: str) -> list[DolDatasetFile]:
    candidates: dict[int, list[DolDatasetFile]] = {}
    for href in re.findall(r"href=[\"']([^\"']+)[\"']", html, flags=re.IGNORECASE):
        filename = href.rsplit("/", 1)[-1]
        if not re.search(r"\bLCA[_\s-].*(Disclosure|Dislclosure)", filename, re.IGNORECASE):
            continue
        if re.search(r"Appendix|Worksites|Record_Layout", filename, re.IGNORECASE):
            continue
        match = re.search(r"FY(20\d{2})(?:_Q([1-4]))?", filename, re.IGNORECASE)
        if not match:
            continue
        fy = int(match.group(1))
        quarter = int(match.group(2)) if match.group(2) else None
        candidates.setdefault(fy, []).append(DolDatasetFile(fy=fy, quarter=quarter, url=urljoin(DOL_BASE_URL, href)))

    if not candidates:
        return []

    latest_fy = max(candidates)
    selected: list[DolDatasetFile] = []
    for fy in [latest_fy, latest_fy - 1, latest_fy - 2]:
        files = candidates.get(fy, [])
        if not files:
            continue
        if fy == latest_fy:
            selected.append(max(files, key=lambda item: item.quarter or 0))
        else:
            full_years = [item for item in files if item.quarter is None]
            selected.append(full_years[0] if full_years else max(files, key=lambda item: item.quarter or 0))
    return selected


def dol_manifest_fingerprint(files: list[DolDatasetFile]) -> str:
    payload = [
        {"fy": item.fy, "quarter": item.quarter, "url": item.url}
        for item in sorted(files, key=lambda item: (item.fy, item.quarter or 0), reverse=True)
    ]
    normalized = json.dumps(
        {"index_schema_version": INDEX_SCHEMA_VERSION, "files": payload},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def normalize_employer_name(value: str) -> str:
    normalized = value.upper().replace("&", " AND ")
    normalized = re.sub(r"[^A-Z0-9]+", " ", normalized)
    tokens = [token for token in normalized.split() if token not in _CORPORATE_SUFFIX_TOKENS]
    return " ".join(tokens)


def _query_history(index_path: Path, normalized: str, fingerprint: str, warnings: list[str]) -> DolHistoryResult:
    if not index_path.exists():
        return DolHistoryResult(manifest_fingerprint=fingerprint, warnings=warnings)

    match_where, match_params = _employer_match_predicate(normalized)
    connection = sqlite3.connect(index_path)
    try:
        connection.row_factory = sqlite3.Row
        match_count = connection.execute(
            f"""
            SELECT COUNT(*)
            FROM lca_cases
            WHERE {match_where}
            """,
            match_params,
        ).fetchone()[0]
        recent_rows = connection.execute(
            f"""
            SELECT case_status, decision_date
            FROM lca_cases
            WHERE {match_where}
            """,
            match_params,
        ).fetchall()
        evidence_rows = connection.execute(
            f"""
            SELECT fy, employer_name, job_title, soc_code, worksite, case_status, decision_date,
                   CASE WHEN normalized_employer = ? THEN 'employer_exact' ELSE 'employer_alias' END AS matched_by
            FROM lca_cases
            WHERE {match_where}
            ORDER BY decision_date DESC
            LIMIT 5
            """,
            (normalized, *match_params),
        ).fetchall()
    finally:
        connection.close()

    recent_cutoff = datetime.now(UTC).date() - timedelta(days=730)
    evidence: list[dict[str, Any]] = []
    for row in evidence_rows:
        item = dict(row)
        decision_date = _parse_date(str(item.get("decision_date", "")))
        if decision_date:
            item["decision_date"] = decision_date.isoformat()
        evidence.append(item)
    recent_certified = 0
    for row in recent_rows:
        decision_date = _parse_date(row["decision_date"])
        if decision_date and decision_date >= recent_cutoff and row["case_status"].strip().lower() == "certified":
            recent_certified += 1

    return DolHistoryResult(
        manifest_fingerprint=fingerprint,
        warnings=warnings,
        match_count=match_count,
        recent_certified_count=recent_certified,
        evidence=evidence,
    )


def _employer_match_predicate(normalized: str) -> tuple[str, tuple[str, ...]]:
    if not normalized.split():
        return "normalized_employer = ?", (normalized,)

    predicates = ["normalized_employer = ?"]
    params = [normalized]
    if len(normalized) >= 4:
        predicates.append("normalized_employer LIKE ?")
        params.append(f"{normalized} %")

    return " OR ".join(predicates), tuple(params)


def _active_index_path_from_manifest(cache_dir: Path) -> Path:
    try:
        manifest = json.loads((cache_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return cache_dir / "active.sqlite3"
    if not isinstance(manifest, dict):
        return cache_dir / "active.sqlite3"
    return Path(str(manifest.get("active_index") or cache_dir / "active.sqlite3"))


def _parse_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _parse_date(value: str):
    value = value.strip()
    if not value:
        return None
    excel_date = _parse_excel_serial_date(value)
    if excel_date:
        return excel_date
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(value[:10], fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def _parse_excel_serial_date(value: str) -> date | None:
    if not re.fullmatch(r"\d+(?:\.\d+)?", value):
        return None
    try:
        serial_float = float(value)
    except ValueError:
        return None
    serial = int(serial_float)
    if serial < 20000 or serial > 80000:
        return None
    return date(1899, 12, 30) + timedelta(days=serial)
