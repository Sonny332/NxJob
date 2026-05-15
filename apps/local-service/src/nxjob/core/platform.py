from __future__ import annotations

import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class PlatformInfo:
    name: str
    is_windows: bool
    is_macos: bool
    is_linux: bool


def current_platform() -> PlatformInfo:
    return PlatformInfo(
        name=sys.platform,
        is_windows=sys.platform == "win32",
        is_macos=sys.platform == "darwin",
        is_linux=sys.platform.startswith("linux"),
    )

