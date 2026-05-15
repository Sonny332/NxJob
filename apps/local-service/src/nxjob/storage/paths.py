from __future__ import annotations

import os
import sys
from pathlib import Path


def app_data_dir(app_name: str = "NxJob") -> Path:
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        return Path(base) / app_name if base else Path.home() / "AppData" / "Local" / app_name

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / app_name

    base = os.environ.get("XDG_DATA_HOME")
    return Path(base) / app_name if base else Path.home() / ".local" / "share" / app_name


def generated_resume_dir() -> Path:
    configured = os.environ.get("NXJOB_GENERATED_RESUME_DIR")
    if configured:
        return Path(configured)
    raise RuntimeError("Resume output folder is not configured.")


def log_dir() -> Path:
    return app_data_dir() / "logs"

