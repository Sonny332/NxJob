from __future__ import annotations

import uvicorn
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from nxjob import __version__
from nxjob.api.applications import router as applications_router
from nxjob.api.health import router as health_router
from nxjob.api.job_leads import router as job_leads_router
from nxjob.api.resumes import router as resumes_router
from nxjob.api.resume_versions import router as resume_versions_router
from nxjob.api.sponsorship import router as sponsorship_router
from nxjob.db.migrations import initialize_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="NxJob Local Service",
        version=__version__,
        description="Local runtime service for NxJob browser extension workflows.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^(chrome-extension://.*|http://localhost:\d+|http://127\.0\.0\.1:\d+)$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(job_leads_router)
    app.include_router(resume_versions_router)
    app.include_router(resumes_router)
    app.include_router(applications_router)
    app.include_router(sponsorship_router)
    return app


app = create_app()


def run() -> None:
    uvicorn.run("nxjob.main:app", host="127.0.0.1", port=8765, reload=False)


if __name__ == "__main__":
    run()

