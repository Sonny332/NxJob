from __future__ import annotations

import re
from dataclasses import dataclass

from nxjob.schemas.core import (
    SponsorshipAnalyzeRequest,
    SponsorshipAnalyzeResponse,
    SponsorshipEvidenceItem,
    SponsorshipSummary,
    SponsorshipStatus,
)

WORKFLOW_NAME = "analyze_sponsorship"


@dataclass(frozen=True)
class Rule:
    pattern: re.Pattern[str]
    status: SponsorshipStatus
    confidence: float
    summary: str


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
        return _ai_fallback_response(ambiguous_match)

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


def _ai_fallback_response(
    ambiguous_match: tuple[Rule, str, str] | None,
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
            source="ai_inference",
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
        ai_used=True,
    )


def _excerpt(text: str, start: int, end: int, radius: int = 90) -> str:
    snippet_start = max(start - radius, 0)
    snippet_end = min(end + radius, len(text))
    snippet = text[snippet_start:snippet_end]
    return " ".join(snippet.split())
