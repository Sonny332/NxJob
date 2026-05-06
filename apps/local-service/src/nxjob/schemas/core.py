from __future__ import annotations

from typing import Any, Literal

from pydantic import AnyUrl, BaseModel, Field

ApplicationStatus = Literal[
    "captured",
    "reviewing",
    "skipped",
    "tailored",
    "ready_to_apply",
    "applied",
    "replied",
    "interviewing",
    "offer",
    "rejected",
    "closed",
]

SourceSite = Literal["linkedin", "indeed", "company_ats", "other"]
ApplicationMethod = Literal["easy_apply", "external_ats", "email", "other"]
ResumeFormat = Literal["docx"]
WorkflowName = Literal[
    "analyze_sponsorship",
    "tailor_resume",
    "draft_form_answer_from_resume_bullets",
]


class TraceResponse(BaseModel):
    trace_id: str


class JobLeadCapture(BaseModel):
    source_url: AnyUrl
    source_site: SourceSite = "other"
    page_title: str = ""
    selected_text: str = ""
    page_text_excerpt: str = ""
    platform_insights: dict[str, Any] = Field(default_factory=dict)
    search_query: str = ""
    user_notes: str = ""


class JobLeadRecord(BaseModel):
    id: str
    source_url: str
    source_site: str
    page_title: str
    company_name: str
    job_title: str
    location: str
    captured_at: str
    jd_text: str
    jd_hash: str
    platform_insights: dict[str, Any]
    search_query: str
    status: str
    user_notes: str


class JobLeadCaptureResponse(TraceResponse):
    job_lead: JobLeadRecord
    dedupe: dict[str, Any]


class ResumeVersionCreate(BaseModel):
    job_lead_id: str
    source_master_resume_id: str = ""
    format: ResumeFormat = "docx"
    file_path: str
    selected_bullets: list[str] = Field(default_factory=list)
    change_summary: str = ""
    ai_output: dict[str, Any] = Field(default_factory=dict)
    prompt_log_id: str = ""
    version_label: str = ""
    user_approved: bool = False


class ResumeVersionRecord(ResumeVersionCreate):
    id: str
    created_at: str


class ResumeVersionResponse(TraceResponse):
    resume_version: ResumeVersionRecord


class ApplicationCreate(BaseModel):
    job_lead_id: str
    resume_version_id: str | None = None
    applied_at: str = ""
    application_url: AnyUrl
    application_method: ApplicationMethod = "external_ats"
    submitted_by_user: bool = True
    follow_up_at: str = ""
    user_notes: str = ""


class ApplicationRecord(BaseModel):
    id: str
    job_lead_id: str
    resume_version_id: str | None
    applied_at: str
    application_url: str
    application_method: str
    status: str
    submitted_by_user: bool
    follow_up_at: str
    user_notes: str


class ApplicationResponse(TraceResponse):
    application: ApplicationRecord


class WorkflowTraceRecord(BaseModel):
    trace_id: str
    workflow_name: WorkflowName
    created_at: str
    input_summary: str = ""
    output_summary: str = ""
    status: Literal["started", "completed", "failed"] = "completed"

