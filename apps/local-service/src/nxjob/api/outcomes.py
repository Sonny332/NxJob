from __future__ import annotations

from fastapi import APIRouter, HTTPException

from nxjob.core.trace import new_trace_id
from nxjob.db.connection import db_session
from nxjob.db.repositories import (
    create_outcome_signal,
    create_success_reference,
    get_application,
    get_job_lead,
    get_latest_resume_version_for_job,
    get_resume_version,
    get_success_reference,
    list_outcome_signals_for_job,
    list_success_references_for_tracker,
    update_application_status,
    update_job_lead_status,
)
from nxjob.schemas.core import (
    OutcomeSignalCreate,
    OutcomeSignalListResponse,
    OutcomeSignalResponse,
    SuccessReferenceCreate,
    SuccessReferenceDetail,
    SuccessReferenceDetailResponse,
    SuccessReferenceListResponse,
)
from nxjob.workflows.resume_tailor import extract_keywords

router = APIRouter(prefix="/api/v1", tags=["tracking"])

POSITIVE_OUTCOMES = {"positive_reply", "screen", "interview", "offer"}
APPLICATION_STATUS_BY_OUTCOME = {
    "positive_reply": "replied",
    "screen": "interviewing",
    "interview": "interviewing",
    "offer": "offer",
    "rejection": "rejected",
    "no_response": "closed",
    "closed": "closed",
}


@router.post("/outcomes", response_model=OutcomeSignalResponse)
def create_outcome_endpoint(payload: OutcomeSignalCreate) -> OutcomeSignalResponse:
    trace_id = new_trace_id()

    with db_session() as connection:
        try:
            job_lead = get_job_lead(connection, payload.job_lead_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="JobLead not found") from exc

        application = None
        if payload.application_id:
            try:
                application = get_application(connection, payload.application_id)
            except KeyError as exc:
                raise HTTPException(status_code=404, detail="Application not found") from exc
            if application.job_lead_id != payload.job_lead_id:
                raise HTTPException(status_code=422, detail="Application does not belong to JobLead")

        outcome = create_outcome_signal(connection, payload)
        status = APPLICATION_STATUS_BY_OUTCOME[payload.outcome_type]
        update_job_lead_status(connection, payload.job_lead_id, status)
        if application:
            update_application_status(connection, application.id, status)

        success_reference = None
        if payload.outcome_type in POSITIVE_OUTCOMES:
            resume_version_id = application.resume_version_id if application else None
            resume_version = (
                get_resume_version(connection, resume_version_id)
                if resume_version_id
                else get_latest_resume_version_for_job(connection, payload.job_lead_id)
            )
            if resume_version is not None:
                success_reference = create_success_reference(
                    connection,
                    SuccessReferenceCreate(
                        application_id=payload.application_id,
                        job_lead_id=payload.job_lead_id,
                        resume_version_id=resume_version.id,
                        outcome_type=payload.outcome_type,
                        outcome_at=outcome.outcome_at,
                        source=payload.source,
                        search_query=job_lead.search_query,
                        effective_keywords=extract_keywords(job_lead.jd_text, limit=16),
                        effective_bullets=resume_version.selected_bullets,
                        user_notes=payload.user_notes,
                    ),
                )

    return OutcomeSignalResponse(
        trace_id=trace_id,
        outcome=outcome,
        success_reference={
            "created": success_reference is not None,
            "id": success_reference.id if success_reference else "",
        },
    )


@router.get("/outcomes", response_model=OutcomeSignalListResponse)
def list_outcomes_endpoint(job_lead_id: str = "", limit: int = 20) -> OutcomeSignalListResponse:
    trace_id = new_trace_id()
    with db_session() as connection:
        outcomes = (
            list_outcome_signals_for_job(connection, job_lead_id, max(1, min(limit, 100)))
            if job_lead_id
            else []
        )
    return OutcomeSignalListResponse(trace_id=trace_id, outcomes=outcomes)


@router.get("/success-references", response_model=SuccessReferenceListResponse)
def list_success_references_endpoint(limit: int = 50) -> SuccessReferenceListResponse:
    trace_id = new_trace_id()
    with db_session() as connection:
        references = list_success_references_for_tracker(connection, max(1, min(limit, 100)))
    return SuccessReferenceListResponse(trace_id=trace_id, success_references=references)


@router.get("/success-references/{success_reference_id}", response_model=SuccessReferenceDetailResponse)
def read_success_reference_endpoint(success_reference_id: str) -> SuccessReferenceDetailResponse:
    trace_id = new_trace_id()
    with db_session() as connection:
        try:
            reference = get_success_reference(connection, success_reference_id)
            job_lead = get_job_lead(connection, reference.job_lead_id)
            resume_version = get_resume_version(connection, reference.resume_version_id)
            application = get_application(connection, reference.application_id) if reference.application_id else None
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="SuccessReference not found") from exc

    return SuccessReferenceDetailResponse(
        trace_id=trace_id,
        detail=SuccessReferenceDetail(
            success_reference=reference,
            job_lead=job_lead,
            resume_version=resume_version,
            application=application,
        ),
    )
