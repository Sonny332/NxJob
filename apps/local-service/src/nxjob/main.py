from __future__ import annotations

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from nxjob import __version__
from nxjob.api.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="NxJob Local Service",
        version=__version__,
        description="Local runtime service for NxJob browser extension workflows.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^(chrome-extension://.*|http://localhost:\d+|http://127\.0\.0\.1:\d+)$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    return app


app = create_app()


def run() -> None:
    uvicorn.run("nxjob.main:app", host="127.0.0.1", port=8765, reload=False)


if __name__ == "__main__":
    run()

