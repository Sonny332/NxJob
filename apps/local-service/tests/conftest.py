from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolate_user_private_config(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    monkeypatch.delenv("NXJOB_AI_API_KEY", raising=False)
    monkeypatch.delenv("NXJOB_AI_PROVIDER", raising=False)
    monkeypatch.delenv("NXJOB_AI_BASE_URL", raising=False)
    monkeypatch.delenv("NXJOB_AI_MODEL", raising=False)
    monkeypatch.delenv("NXJOB_MASTER_RESUME_PATH", raising=False)
