from __future__ import annotations

import json
from pathlib import Path

from nxjob.schemas.core import MasterResumeProfile
from nxjob.settings.private_config import configured_master_resume_path


class MasterResumeNotConfiguredError(RuntimeError):
    pass


def master_resume_path() -> Path:
    configured = configured_master_resume_path()
    if configured is None:
        raise MasterResumeNotConfiguredError("Master resume is not configured.")
    return configured


def load_master_resume() -> MasterResumeProfile:
    path = master_resume_path()
    if not path.exists():
        raise MasterResumeNotConfiguredError(f"Master resume file does not exist: {path}")

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return MasterResumeProfile.model_validate(data)
