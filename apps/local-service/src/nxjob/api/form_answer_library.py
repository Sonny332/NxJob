from __future__ import annotations

from fastapi import APIRouter, HTTPException

from nxjob.core.trace import new_trace_id
from nxjob.schemas.core import (
    SavedAnswerCreate,
    SavedAnswerResponse,
    SavedAnswerUpdate,
    SavedAnswersImportRequest,
    SavedAnswersResponse,
    TraceResponse,
)
from nxjob.settings.private_config import (
    PrivateConfigError,
    PrivateConfigNotFoundError,
    clear_saved_answers,
    create_saved_answer,
    delete_saved_answer,
    import_saved_answers,
    list_saved_answers,
    touch_saved_answer,
    update_saved_answer,
)


router = APIRouter(prefix="/api/v1/form-answer-library", tags=["form-answer-library"])


@router.get("", response_model=SavedAnswersResponse)
def read_saved_answers() -> SavedAnswersResponse:
    try:
        answers = list_saved_answers()
    except PrivateConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return SavedAnswersResponse(trace_id=new_trace_id(), version=1, answers=answers)


@router.post("", response_model=SavedAnswerResponse)
def create_saved_answer_record(payload: SavedAnswerCreate) -> SavedAnswerResponse:
    try:
        answer = create_saved_answer(payload)
    except PrivateConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return SavedAnswerResponse(trace_id=new_trace_id(), answer=answer)


@router.put("/{answer_id}", response_model=SavedAnswerResponse)
def update_saved_answer_record(answer_id: str, payload: SavedAnswerUpdate) -> SavedAnswerResponse:
    try:
        answer = update_saved_answer(answer_id, payload)
    except PrivateConfigNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PrivateConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return SavedAnswerResponse(trace_id=new_trace_id(), answer=answer)


@router.post("/{answer_id}/touch", response_model=SavedAnswerResponse)
def touch_saved_answer_record(answer_id: str) -> SavedAnswerResponse:
    try:
        answer = touch_saved_answer(answer_id)
    except PrivateConfigNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PrivateConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return SavedAnswerResponse(trace_id=new_trace_id(), answer=answer)


@router.delete("/{answer_id}", response_model=TraceResponse)
def delete_saved_answer_record(answer_id: str) -> TraceResponse:
    try:
        delete_saved_answer(answer_id)
    except PrivateConfigNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PrivateConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return TraceResponse(trace_id=new_trace_id())


@router.delete("", response_model=TraceResponse)
def clear_saved_answer_records() -> TraceResponse:
    try:
        clear_saved_answers()
    except PrivateConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return TraceResponse(trace_id=new_trace_id())


@router.post("/import", response_model=SavedAnswersResponse)
def import_saved_answer_records(payload: SavedAnswersImportRequest) -> SavedAnswersResponse:
    try:
        answers = import_saved_answers(payload.answers)
    except PrivateConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return SavedAnswersResponse(trace_id=new_trace_id(), version=1, answers=answers)
