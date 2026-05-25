from __future__ import annotations

import os
from pathlib import Path
import sys
from uuid import uuid4


def _patch_windows_mkdir_mode() -> None:
    """Avoid Python 3.14 temp-dir ACL breakage on this Windows worker host."""

    original_mkdir = os.mkdir

    def mkdir_without_restrictive_mode(path, mode=0o777, *args, **kwargs):  # noqa: ANN001
        if os.name == "nt":
            return original_mkdir(path, *args, **kwargs)
        return original_mkdir(path, mode, *args, **kwargs)

    os.mkdir = mkdir_without_restrictive_mode


def _has_option(args: list[str], name: str) -> bool:
    return any(arg == name or arg.startswith(f"{name}=") for arg in args)


def main(argv: list[str]) -> int:
    repo_root = Path(__file__).resolve().parents[1]

    _patch_windows_mkdir_mode()
    default_temp_parent = Path(os.environ.get("TEMP") or os.environ.get("TMP") or repo_root)
    runtime_root = Path(os.environ.get("NXJOB_PYTEST_RUNTIME_ROOT", default_temp_parent / "NxJobPytest"))
    runtime_root.mkdir(parents=True, exist_ok=True)

    import tempfile

    tempfile.tempdir = str(runtime_root)
    os.environ["TMP"] = str(runtime_root)
    os.environ["TEMP"] = str(runtime_root)
    os.environ["TMPDIR"] = str(runtime_root)

    pytest_args = list(argv)
    if not _has_option(pytest_args, "--basetemp"):
        pytest_args.extend(["--basetemp", str(runtime_root / f"basetemp-{uuid4().hex}")])
    if "-p" not in pytest_args and not any(arg.startswith("-p") for arg in pytest_args):
        pytest_args.extend(["-p", "no:cacheprovider"])

    print(f"NxJob pytest wrapper: temp_root={runtime_root}")

    import pytest

    return int(pytest.main(pytest_args))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
