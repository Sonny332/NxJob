from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DocumentValidationResult:
    is_valid: bool
    backend: str
    warnings: list[str]


def validate_docx_basic(path: Path) -> DocumentValidationResult:
    exists = path.exists() and path.suffix.lower() == ".docx"
    return DocumentValidationResult(
        is_valid=exists,
        backend="basic-path-check",
        warnings=[] if exists else ["DOCX file does not exist or has an invalid extension."],
    )

