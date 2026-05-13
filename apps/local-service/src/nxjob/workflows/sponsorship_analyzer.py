from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from nxjob.ai.openai_compatible import AiProviderError, request_json_object
from nxjob.schemas.core import (
    SponsorshipAnalyzeRequest,
    SponsorshipAnalyzeResponse,
    SponsorshipEvidenceItem,
    SponsorshipSummary,
    SponsorshipStatus,
)
from nxjob.settings.private_config import AiProviderConfig

WORKFLOW_NAME = "analyze_sponsorship"
VALID_SPONSORSHIP_STATUSES: set[SponsorshipStatus] = {
    "supports",
    "does_not_support",
    "likely_supports",
    "likely_not_supports",
    "needs_confirmation",
    "unknown",
}


@dataclass(frozen=True)
class Rule:
    pattern: re.Pattern[str]
    status: SponsorshipStatus
    confidence: float
    summary: str


@dataclass(frozen=True)
class AiSponsorshipResult:
    response: SponsorshipAnalyzeResponse
    token_usage: dict[str, Any]
    provider: str
    model: str


EXPLICIT_NEGATIVE_RULES = [
    Rule(
        re.compile(
            r"\b(will\s+not|do\s+not|does\s+not|cannot|can't|unable\s+to)\s+sponsor\b",
            re.IGNORECASE,
        ),
        "does_not_support",
        0.95,
        "The posting explicitly says sponsorship is not available.",
    ),
    Rule(
        re.compile(
            r"\b(no\s+visa\s+sponsorship|(?:visa\s+)?sponsorship\s+(is\s+)?not\s+available|not\s+eligible\s+for\s+(?:visa\s+)?sponsorship)\b",
            re.IGNORECASE,
        ),
        "does_not_support",
        0.94,
        "The posting explicitly excludes visa sponsorship.",
    ),
]

EXPLICIT_POSITIVE_RULES = [
    Rule(
        re.compile(
            r"\b(will\s+sponsor|we\s+sponsor|visa\s+sponsorship\s+is\s+available|sponsorship\s+available)\b",
            re.IGNORECASE,
        ),
        "supports",
        0.92,
        "The posting explicitly says sponsorship is available.",
    ),
    Rule(
        re.compile(
            r"\b(sponsor\s+qualified\s+candidates|eligible\s+for\s+h-?1b\s+sponsorship)\b",
            re.IGNORECASE,
        ),
        "supports",
        0.88,
        "The posting indicates qualified candidates may receive sponsorship.",
    ),
]

LIKELY_NEGATIVE_RULES = [
    Rule(
        re.compile(
            r"\b(authorized\s+to\s+work|work\s+authorization).{0,80}\bwithout\s+(?:visa\s+)?sponsorship\b",
            re.IGNORECASE | re.DOTALL,
        ),
        "likely_not_supports",
        0.78,
        "The posting requires work authorization without sponsorship.",
    ),
    Rule(
        re.compile(
            r"\b(without\s+(?:visa\s+)?sponsorship).{0,80}\b(now\s+or\s+in\s+the\s+future)\b",
            re.IGNORECASE | re.DOTALL,
        ),
        "likely_not_supports",
        0.76,
        "The wording suggests candidates needing sponsorship may be filtered out.",
    ),
]

AMBIGUOUS_RULES = [
    Rule(
        re.compile(r"\b(must\s+be\s+)?authorized\s+to\s+work\b", re.IGNORECASE),
        "needs_confirmation",
        0.48,
        "The posting mentions work authorization but does not clearly state sponsorship support.",
    ),
    Rule(
        re.compile(r"\b(now\s+or\s+in\s+the\s+future)\b", re.IGNORECASE),
        "needs_confirmation",
        0.45,
        "The text contains sponsorship-screening wording, but the final policy is unclear.",
    ),
]


def analyze_sponsorship(payload: SponsorshipAnalyzeRequest, jd_text: str) -> SponsorshipAnalyzeResponse:
    sources = [
        ("jd_text", jd_text),
        ("application_form_text", payload.application_form_text),
    ]

    for rules in (EXPLICIT_NEGATIVE_RULES, EXPLICIT_POSITIVE_RULES, LIKELY_NEGATIVE_RULES):
        match = _first_match(rules, sources)
        if match:
            rule, source, evidence_text = match
            return _rule_response(rule, source, evidence_text, ai_used=False)

    ambiguous_match = _first_match(AMBIGUOUS_RULES, sources)
    if ambiguous_match and not payload.allow_ai:
        rule, source, evidence_text = ambiguous_match
        return _rule_response(
            rule,
            source,
            evidence_text,
            ai_used=False,
            risk_flags=["Sponsorship support is not explicit."],
        )

    if payload.allow_ai:
        return _uncertain_response(ambiguous_match, source="local_uncertain")

    return SponsorshipAnalyzeResponse(
        trace_id="",
        sponsorship=SponsorshipSummary(
            status="unknown",
            confidence=0.2,
            summary="No local sponsorship signal was found in the provided text.",
            risk_flags=["No explicit sponsorship evidence found."],
            questions_to_confirm=["Does the employer sponsor this role now or in the future?"],
            is_legal_conclusion=False,
        ),
        evidence=[
            SponsorshipEvidenceItem(
                source="jd_text",
                evidence_text="No deterministic local sponsorship signal was found.",
                confidence=0.2,
            )
        ],
        ai_used=False,
    )


def analyze_sponsorship_with_ai(
    payload: SponsorshipAnalyzeRequest,
    jd_text: str,
    baseline: SponsorshipAnalyzeResponse,
    ai_config: AiProviderConfig,
) -> AiSponsorshipResult:
    result = request_json_object(ai_config, _ai_messages(payload, jd_text, baseline), timeout_seconds=45)
    response = _response_from_ai_payload(result.data, baseline)
    return AiSponsorshipResult(
        response=response,
        token_usage=result.token_usage,
        provider=result.provider,
        model=result.model,
    )


def add_ai_unavailable_evidence(
    baseline: SponsorshipAnalyzeResponse,
    error: AiProviderError | None = None,
) -> SponsorshipAnalyzeResponse:
    evidence_text = (
        error.user_message
        if error is not None
        else "AI sponsorship fallback was requested, but no AI provider is configured."
    )
    risk_flags = [*baseline.sponsorship.risk_flags]
    if "AI fallback could not complete; confirm sponsorship before prioritizing this role." not in risk_flags:
        risk_flags.append("AI fallback could not complete; confirm sponsorship before prioritizing this role.")

    evidence = [
        *baseline.evidence,
        SponsorshipEvidenceItem(
            source="ai_provider_error" if error is not None else "ai_config_missing",
            evidence_text=evidence_text,
            confidence=baseline.sponsorship.confidence,
        ),
    ]
    return baseline.model_copy(
        update={
            "sponsorship": baseline.sponsorship.model_copy(update={"risk_flags": risk_flags}),
            "evidence": evidence,
            "ai_used": False,
        }
    )


def _first_match(
    rules: list[Rule],
    sources: list[tuple[str, str]],
) -> tuple[Rule, str, str] | None:
    for source, text in sources:
        if not text:
            continue
        for rule in rules:
            match = rule.pattern.search(text)
            if match:
                return rule, source, _excerpt(text, match.start(), match.end())
    return None


def _rule_response(
    rule: Rule,
    source: str,
    evidence_text: str,
    ai_used: bool,
    risk_flags: list[str] | None = None,
) -> SponsorshipAnalyzeResponse:
    questions = []
    if rule.status in {"likely_not_supports", "needs_confirmation"}:
        questions.append("Can the employer confirm sponsorship support for this role?")

    return SponsorshipAnalyzeResponse(
        trace_id="",
        sponsorship=SponsorshipSummary(
            status=rule.status,
            confidence=rule.confidence,
            summary=rule.summary,
            risk_flags=risk_flags or [],
            questions_to_confirm=questions,
            is_legal_conclusion=False,
        ),
        evidence=[
            SponsorshipEvidenceItem(
                source=source,
                evidence_text=evidence_text,
                confidence=rule.confidence,
            )
        ],
        ai_used=ai_used,
    )


def _uncertain_response(
    ambiguous_match: tuple[Rule, str, str] | None,
    source: str,
) -> SponsorshipAnalyzeResponse:
    evidence = []
    confidence = 0.42
    summary = "The provided text does not clearly confirm sponsorship support."

    if ambiguous_match:
        rule, source, evidence_text = ambiguous_match
        confidence = 0.55
        summary = "The wording is ambiguous and should be confirmed before prioritizing this role."
        evidence.append(
            SponsorshipEvidenceItem(
                source=source,
                evidence_text=evidence_text,
                confidence=rule.confidence,
            )
        )

    evidence.append(
        SponsorshipEvidenceItem(
            source=source,
            evidence_text="No deterministic local rule could confirm sponsorship support.",
            confidence=confidence,
        )
    )

    return SponsorshipAnalyzeResponse(
        trace_id="",
        sponsorship=SponsorshipSummary(
            status="needs_confirmation",
            confidence=confidence,
            summary=summary,
            risk_flags=["AI fallback is only a probability estimate, not a legal conclusion."],
            questions_to_confirm=[
                "Does this role support visa sponsorship now or in the future?",
                "Is sponsorship available for the specific location and employment type?",
            ],
            is_legal_conclusion=False,
        ),
        evidence=evidence,
        ai_used=False,
    )


def _ai_messages(
    payload: SponsorshipAnalyzeRequest,
    jd_text: str,
    baseline: SponsorshipAnalyzeResponse,
) -> list[dict[str, str]]:
    system = (
        "You are NxJob Sponsorship Analyzer. Return only a JSON object. "
        "Classify whether this job posting appears to support work visa sponsorship. "
        "Use only the supplied job description and form text. Do not provide legal advice. "
        "Allowed statuses: supports, does_not_support, likely_supports, likely_not_supports, "
        "needs_confirmation, unknown. Prefer needs_confirmation when evidence is ambiguous."
    )
    user = {
        "output_schema": {
            "status": "one allowed status",
            "confidence": "number from 0 to 1",
            "summary": "short user-facing summary",
            "evidence": "short excerpt or reasoning from the supplied text",
            "risk_flags": ["short risk flag"],
            "questions_to_confirm": ["short question for recruiter or application form"],
        },
        "job": {
            "company_name": payload.company_name,
            "job_url": payload.job_url,
            "jd_text": jd_text[:12000],
            "application_form_text": payload.application_form_text[:4000],
        },
        "local_baseline": {
            "status": baseline.sponsorship.status,
            "confidence": baseline.sponsorship.confidence,
            "summary": baseline.sponsorship.summary,
            "evidence": [item.model_dump() for item in baseline.evidence],
        },
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": _compact_json(user)},
    ]


def _response_from_ai_payload(
    payload: dict[str, Any],
    baseline: SponsorshipAnalyzeResponse,
) -> SponsorshipAnalyzeResponse:
    status = str(payload.get("status", "")).strip().lower()
    if status not in VALID_SPONSORSHIP_STATUSES:
        status = "needs_confirmation"

    confidence = _confidence(payload.get("confidence"), baseline.sponsorship.confidence)
    summary = str(payload.get("summary", "")).strip() or baseline.sponsorship.summary
    evidence_text = str(payload.get("evidence", "")).strip() or "AI inferred sponsorship likelihood from the supplied JD."
    risk_flags = _string_list(payload.get("risk_flags"))
    questions = _string_list(payload.get("questions_to_confirm"))
    if not questions and status in {"likely_not_supports", "needs_confirmation", "unknown"}:
        questions = [
            "Does this role support visa sponsorship now or in the future?",
            "Is sponsorship available for the specific location and employment type?",
        ]
    if "Not a legal conclusion." not in risk_flags:
        risk_flags.append("Not a legal conclusion.")

    return SponsorshipAnalyzeResponse(
        trace_id="",
        sponsorship=SponsorshipSummary(
            status=status,  # type: ignore[arg-type]
            confidence=confidence,
            summary=summary,
            risk_flags=risk_flags,
            questions_to_confirm=questions,
            is_legal_conclusion=False,
        ),
        evidence=[
            *baseline.evidence,
            SponsorshipEvidenceItem(
                source="ai_inference",
                evidence_text=evidence_text,
                confidence=confidence,
            ),
        ],
        ai_used=True,
    )


def _confidence(value: object, fallback: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = fallback
    return min(max(parsed, 0.0), 1.0)


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _compact_json(value: object) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _excerpt(text: str, start: int, end: int, radius: int = 90) -> str:
    snippet_start = max(start - radius, 0)
    snippet_end = min(end + radius, len(text))
    snippet = text[snippet_start:snippet_end]
    return " ".join(snippet.split())
