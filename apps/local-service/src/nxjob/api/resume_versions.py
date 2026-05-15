from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from nxjob.core.trace import new_trace_id
from nxjob.db.connection import db_session
from nxjob.db.repositories import create_resume_version, get_resume_version
from nxjob.schemas.core import ResumeVersionCreate, ResumeVersionRecord, ResumeVersionResponse
from nxjob.settings.private_config import configured_resume_output_dir

router = APIRouter(prefix="/api/v1/resume-versions", tags=["resume-versions"])


@router.post("", response_model=ResumeVersionResponse)
def create_resume_version_endpoint(payload: ResumeVersionCreate) -> ResumeVersionResponse:
    trace_id = new_trace_id()
    with db_session() as connection:
        try:
            record = create_resume_version(connection, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Referenced record not found") from exc

    return ResumeVersionResponse(trace_id=trace_id, resume_version=record)


@router.get("/{resume_version_id}", response_model=ResumeVersionRecord)
def read_resume_version(resume_version_id: str) -> ResumeVersionRecord:
    with db_session() as connection:
        try:
            return get_resume_version(connection, resume_version_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="ResumeVersion not found") from exc


@router.get("/{resume_version_id}/artifacts/{artifact_type}")
def read_resume_version_artifact(
    resume_version_id: str,
    artifact_type: Literal["docx", "markdown"],
) -> FileResponse:
    with db_session() as connection:
        try:
            resume_version = get_resume_version(connection, resume_version_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="ResumeVersion not found") from exc

    path = _registered_artifact_path(resume_version, artifact_type)
    _validate_artifact_under_output_dir(path)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Resume artifact file is missing.")

    media_type = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if artifact_type == "docx"
        else "text/markdown; charset=utf-8"
    )
    return FileResponse(path, media_type=media_type, filename=path.name)


def _registered_artifact_path(
    resume_version: ResumeVersionRecord,
    artifact_type: Literal["docx", "markdown"],
) -> Path:
    if artifact_type == "docx":
        path = Path(resume_version.file_path).expanduser()
        if path.suffix.lower() != ".docx":
            raise HTTPException(status_code=422, detail="Registered DOCX artifact path is invalid.")
        return path

    markdown_path = resume_version.ai_output.get("markdown_path")
    if not isinstance(markdown_path, str) or not markdown_path.strip():
        raise HTTPException(status_code=404, detail="Markdown artifact is not registered for this resume version.")
    path = Path(markdown_path).expanduser()
    if path.suffix.lower() != ".md":
        raise HTTPException(status_code=422, detail="Registered Markdown artifact path is invalid.")
    return path


def _validate_artifact_under_output_dir(path: Path) -> None:
    output_dir = configured_resume_output_dir()
    if output_dir is None:
        raise HTTPException(status_code=422, detail="Resume output folder is not configured.")

    base = output_dir.expanduser().resolve()
    candidate = path.expanduser().resolve(strict=False)
    if candidate != base and base not in candidate.parents:
        raise HTTPException(
            status_code=422,
            detail="Registered resume artifact path is outside configured output folder.",
        )

