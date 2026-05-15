from __future__ import annotations

from nxjob.core.trace import new_trace_id
from nxjob.db.connection import db_session
from nxjob.db.repositories import create_workflow_trace, utc_now
from nxjob.schemas.core import WorkflowName, WorkflowTraceRecord


def record_workflow_trace(
    workflow_name: WorkflowName,
    input_summary: str = "",
    output_summary: str = "",
    status: str = "completed",
) -> WorkflowTraceRecord:
    trace = WorkflowTraceRecord(
        trace_id=new_trace_id(),
        workflow_name=workflow_name,
        created_at=utc_now(),
        input_summary=input_summary,
        output_summary=output_summary,
        status=status,  # type: ignore[arg-type]
    )
    with db_session() as connection:
        return create_workflow_trace(connection, trace)

