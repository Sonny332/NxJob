from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException

from nxjob.ai.openai_compatible import AiProviderError
from nxjob.core.trace import new_trace_id
from nxjob.core.workflow_cache import workflow_cache_key
from nxjob.data.dol_lca_history import (
    INDEX_SCHEMA_VERSION,
    local_dol_lca_cache_fingerprint,
    normalize_employer_name,
    resolve_dol_lca_history,
)
from nxjob.db.connection import db_session
from nxjob.db.repositories import (
    create_prompt_log,
    create_sponsorship_evidence,
    create_workflow_trace,
    create_workflow_result,
    find_cached_workflow_result,
    get_job_lead,
    utc_now,
)
from nxjob.schemas.core import (
    PromptLogCreate,
    SponsorshipAnalyzeRequest,
    SponsorshipAnalyzeResponse,
    WorkflowCacheInfo,
    WorkflowTraceRecord,
)
from nxjob.settings.private_config import read_ai_provider_config, read_ai_provider_status
from nxjob.workflows.sponsorship_analyzer import (
    WORKFLOW_NAME,
    add_ai_unavailable_evidence,
    add_dol_lca_history_evidence,
    analyze_sponsorship,
    analyze_sponsorship_with_ai,
)

router = APIRouter(prefix="/api/v1/sponsorship", tags=["sponsorship"])


@router.post("/analyze", response_model=SponsorshipAnalyzeResponse)
def analyze_sponsorship_endpoint(payload: SponsorshipAnalyzeRequest) -> SponsorshipAnalyzeResponse:
    with db_session() as connection:
        try:
            job_lead = get_job_lead(connection, payload.job_lead_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="JobLead not found") from exc

        jd_text = payload.jd_text or job_lead.jd_text
        if not jd_text:
            raise HTTPException(status_code=422, detail="jd_text or JobLead.jd_text is required")

        effective_employer_name = _effective_dol_employer_name(
            payload.company_name,
            job_lead.company_name,
            job_lead.page_title,
            jd_text,
        )
        normalized_dol_employer = normalize_employer_name(effective_employer_name)
        cache_key = workflow_cache_key(
            WORKFLOW_NAME,
            "v6",
            {
                "jd_hash": job_lead.jd_hash,
                "application_form_text": payload.application_form_text,
                "allow_public_lookup": payload.allow_public_lookup,
                "dol_effective_employer": normalized_dol_employer if payload.allow_public_lookup else "disabled",
                "dol_index_schema_version": INDEX_SCHEMA_VERSION if payload.allow_public_lookup else "disabled",
                "dol_local_cache_fingerprint": (
                    local_dol_lca_cache_fingerprint() if payload.allow_public_lookup else "disabled"
                ),
                "allow_ai": payload.allow_ai,
                "ai_provider": _ai_cache_identity() if payload.allow_ai else "disabled",
            },
        )
        if not payload.force_refresh:
            cached = find_cached_workflow_result(connection, WORKFLOW_NAME, cache_key)
            if cached is not None:
                return SponsorshipAnalyzeResponse.model_validate(cached.response).model_copy(
                    update={"cache": WorkflowCacheInfo(hit=True, cache_key=cache_key)}
                )

        dol_history = (
            resolve_dol_lca_history(effective_employer_name)
            if payload.allow_public_lookup
            else None
        )

        trace_id = new_trace_id()
        analysis = analyze_sponsorship(payload, jd_text)
        if dol_history is not None:
            analysis = add_dol_lca_history_evidence(analysis, dol_history)
        ai_config = read_ai_provider_config() if _should_use_ai(payload, analysis) else None
        (
            _ai_configured,
            _ai_provider_name,
            _ai_model,
            _ai_reasoning_effort,
            _ai_profile_id,
            _ai_profile_display_name,
            ai_provider_source,
        ) = read_ai_provider_status()
        prompt_log_payload: PromptLogCreate | None = None
        if _should_use_ai(payload, analysis):
            if ai_config is None:
                analysis = add_ai_unavailable_evidence(analysis)
            else:
                try:
                    ai_result = analyze_sponsorship_with_ai(payload, jd_text, analysis, ai_config)
                    analysis = ai_result.response
                    prompt_log_payload = PromptLogCreate(
                        trace_id=trace_id,
                        workflow_name=WORKFLOW_NAME,
                        input_summary="JD sponsorship indicators only; full JD not logged",
                        model=ai_result.model,
                        provider=ai_result.provider,
                        token_usage=ai_result.token_usage,
                        output_summary=analysis.sponsorship.status,
                    )
                except AiProviderError as exc:
                    analysis = add_ai_unavailable_evidence(analysis, exc)
                    prompt_log_payload = PromptLogCreate(
                        trace_id=trace_id,
                        workflow_name=WORKFLOW_NAME,
                        input_summary="JD sponsorship indicators only; full JD not logged",
                        model=ai_config.model,
                        provider=ai_config.provider,
                        token_usage={},
                        output_summary="",
                        error=f"{exc.category}; source={ai_provider_source}",
                    )

        analysis = analysis.model_copy(
            update={"trace_id": trace_id, "cache": WorkflowCacheInfo(hit=False, cache_key=cache_key)}
        )
        create_workflow_trace(
            connection,
            WorkflowTraceRecord(
                trace_id=trace_id,
                workflow_name=WORKFLOW_NAME,
                created_at=utc_now(),
                input_summary=f"job_lead_id={payload.job_lead_id}; allow_ai={payload.allow_ai}",
                output_summary=analysis.sponsorship.status,
                status="completed",
            ),
        )
        if prompt_log_payload is not None:
            create_prompt_log(connection, prompt_log_payload)
        create_sponsorship_evidence(connection, payload.job_lead_id, trace_id, analysis)
        create_workflow_result(
            connection,
            job_lead_id=payload.job_lead_id,
            workflow_name=WORKFLOW_NAME,
            cache_key=cache_key,
            trace_id=trace_id,
            status="completed",
            result_summary=analysis.sponsorship.status,
            response=analysis.model_dump(),
        )

    return analysis


def _should_use_ai(payload: SponsorshipAnalyzeRequest, analysis: SponsorshipAnalyzeResponse) -> bool:
    if not payload.allow_ai:
        return False
    if analysis.sponsorship.status in {"needs_confirmation", "unknown"}:
        return True
    return _is_dol_only_likely_supports(analysis)


def _is_dol_only_likely_supports(analysis: SponsorshipAnalyzeResponse) -> bool:
    return (
        analysis.sponsorship.status == "likely_supports"
        and not analysis.ai_used
        and any(item.source == "dol_lca_history" for item in analysis.evidence)
    )


def _ai_cache_identity() -> dict[str, str]:
    config = read_ai_provider_config()
    if config is None:
        return {"provider": "not_configured", "model": ""}
    return {"provider": config.provider, "model": config.model}


def _effective_dol_employer_name(
    payload_company_name: str,
    job_lead_company_name: str,
    page_title: str,
    jd_text: str,
) -> str:
    for candidate in (
        payload_company_name.strip(),
        job_lead_company_name.strip(),
        _company_from_page_title(page_title),
        _company_from_jd_header(jd_text),
    ):
        if candidate:
            return candidate
    return ""


def _company_from_page_title(page_title: str) -> str:
    title = " ".join(page_title.split()).strip()
    if not title:
        return ""

    parts = [part.strip() for part in title.split("|") if part.strip()]
    if len(parts) >= 3 and _is_job_board_suffix(parts[-1]):
        candidate = parts[-2]
        if _looks_like_company_name(candidate):
            return candidate

    title_without_job_board_suffix = _strip_job_board_suffix(title)

    match = re.search(r"\bat\b\s+(?P<company>.+)$", title_without_job_board_suffix, re.IGNORECASE)
    if match:
        candidate = match.group("company").strip(" -|")
        if _looks_like_company_name(candidate):
            return candidate

    if " - " in title_without_job_board_suffix:
        candidate = title_without_job_board_suffix.rsplit(" - ", 1)[-1].strip()
        if _looks_like_company_name(candidate):
            return candidate

    return ""


def _company_from_jd_header(jd_text: str) -> str:
    for raw_line in jd_text.splitlines()[:6]:
        candidate = " ".join(raw_line.split()).strip()
        if _looks_like_company_name(candidate, strict_title_filter=True):
            return candidate
    return ""


def _strip_job_board_suffix(title: str) -> str:
    parts = [part.strip() for part in title.split("|") if part.strip()]
    if len(parts) >= 2 and _is_job_board_suffix(parts[-1]):
        return " | ".join(parts[:-1])
    return title


def _is_job_board_suffix(value: str) -> bool:
    return value.strip().casefold() in {"linkedin", "indeed", "glassdoor"}


def _looks_like_company_name(value: str, *, strict_title_filter: bool = False) -> bool:
    candidate = value.strip(" -|")
    if not candidate:
        return False
    if len(candidate) > 60 or len(candidate.split()) > 8:
        return False
    if any(char in candidate for char in ".?!:;@/\\[]{}"):
        return False
    if "," in candidate:
        return False

    lowered = candidate.casefold()
    if lowered in {
        "linkedin",
        "indeed",
        "glassdoor",
        "about us",
        "about the company",
        "company overview",
        "overview",
        "summary",
        "responsibilities",
        "qualifications",
        "benefits",
    }:
        return False
    if re.search(r"\b(remote|hybrid|on[- ]site|united states|usa|us only|full[- ]time|part[- ]time)\b", lowered):
        return False

    title_keyword_matches = re.findall(
        r"\b(engineer|analyst|developer|scientist|manager|designer|architect|specialist|director|principal|staff|lead|portfolio|recruiter|intern)\b",
        lowered,
    )
    has_legal_suffix = bool(
        re.search(r"\b(inc|llc|corp|corporation|company|co|ltd|plc|gmbh|llp|lp)\b\.?$", lowered)
    )
    if len(title_keyword_matches) >= 2 or (strict_title_filter and title_keyword_matches and not has_legal_suffix):
        return False

    return True
