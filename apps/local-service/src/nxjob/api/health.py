from __future__ import annotations

from fastapi import APIRouter

from nxjob import __version__

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "nxjob-local-service",
        "version": __version__,
    }

