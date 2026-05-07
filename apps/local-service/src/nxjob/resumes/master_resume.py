from __future__ import annotations

import json
import os
from pathlib import Path

from nxjob.schemas.core import MasterResumeProfile


class MasterResumeNotConfiguredError(RuntimeError):
    pass


def master_resume_path() -> Path:
    configured = os.environ.get("NXJOB_MASTER_RESUME_PATH")
    if not configured:
        raise MasterResumeNotConfiguredError("NXJOB_MASTER_RESUME_PATH is not configured.")
    return Path(configured)


def load_master_resume() -> MasterResumeProfile:
    path = master_resume_path()
    if not path.exists():
        raise MasterResumeNotConfiguredError(f"Master resume file does not exist: {path}")

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return MasterResumeProfile.model_validate(data)
