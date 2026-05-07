from __future__ import annotations

import re
from dataclasses import dataclass

from nxjob.schemas.core import (
    JobLeadRecord,
    MasterResumeBullet,
    SuccessReferenceRecord,
    TailoredResumeContent,
)

WORKFLOW_NAME = "tailor_resume"

STOP_WORDS = {
    "and",
    "are",
    "for",
    "from",
    "have",
    "that",
    "the",
    "this",
    "with",
    "you",
    "your",
}


@dataclass(frozen=True)
class TailorDraft:
    content: TailoredResumeContent
    selected_bullet_ids: list[str]
    change_summary: str
    token_usage: dict[str, int]


def tailor_resume_content(
    job_lead: JobLeadRecord,
    bullets: list[MasterResumeBullet],
    success_references: list[SuccessReferenceRecord],
    candidate_name: str = "Candidate",
    contact_line: str = "",
) -> TailorDraft:
    jd_keywords = extract_keywords(job_lead.jd_text)
    success_keywords = [
        keyword
        for reference in success_references
        for keyword in reference.effective_keywords
    ]
    ranked = sorted(
        bullets,
        key=lambda bullet: _bullet_score(bullet, jd_keywords, success_keywords),
        reverse=True,
    )
    selected = [bullet for bullet in ranked if _bullet_score(bullet, jd_keywords, success_keywords) > 0][:6]
    if not selected:
        selected = ranked[: min(6, len(ranked))]

    skills = _skills_from_bullets(selected, jd_keywords)
    summary = _summary_from_keywords(jd_keywords, skills)
    headline = _headline_from_job(job_lead)

    return TailorDraft(
        content=TailoredResumeContent(
            candidate_name=candidate_name or "Candidate",
            contact_line=contact_line,
            headline=headline,
            summary=summary,
            skills=skills,
            experience_bullets=[bullet.text for bullet in selected],
        ),
        selected_bullet_ids=[bullet.id for bullet in selected],
        change_summary=_change_summary(selected, success_references),
        token_usage={
            "input_chars": len(job_lead.jd_text) + sum(len(bullet.text) for bullet in bullets),
            "output_chars": sum(len(bullet.text) for bullet in selected),
        },
    )


def extract_keywords(text: str, limit: int = 24) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9+#.-]{2,}", text.lower())
    counts: dict[str, int] = {}
    for word in words:
        if word in STOP_WORDS:
            continue
        counts[word] = counts.get(word, 0) + 1
    return [
        word
        for word, _ in sorted(counts.items(), key=lambda item: (item[1], item[0]), reverse=True)[:limit]
    ]


def _bullet_score(
    bullet: MasterResumeBullet,
    jd_keywords: list[str],
    success_keywords: list[str],
) -> int:
    text = f"{bullet.text} {' '.join(bullet.tags)}".lower()
    score = sum(3 for keyword in jd_keywords if keyword in text)
    score += sum(2 for keyword in success_keywords if keyword.lower() in text)
    return score


def _skills_from_bullets(selected: list[MasterResumeBullet], jd_keywords: list[str]) -> list[str]:
    tags = []
    for bullet in selected:
        tags.extend(bullet.tags)
    seen = set()
    skills = []
    for value in [*tags, *jd_keywords]:
        normalized = value.strip()
        key = normalized.lower()
        if normalized and key not in seen:
            seen.add(key)
            skills.append(normalized)
    return skills[:12]


def _summary_from_keywords(jd_keywords: list[str], skills: list[str]) -> list[str]:
    focus = ", ".join(skills[:4] or jd_keywords[:4] or ["relevant execution"])
    return [
        f"Focused on roles requiring {focus}.",
        "Selected experience bullets are prioritized for overlap with the current job description.",
    ]


def _headline_from_job(job_lead: JobLeadRecord) -> str:
    if job_lead.job_title and job_lead.company_name:
        return f"{job_lead.job_title} alignment for {job_lead.company_name}"
    if job_lead.job_title:
        return f"{job_lead.job_title} alignment"
    return "Targeted resume for selected job description"


def _change_summary(
    selected: list[MasterResumeBullet],
    success_references: list[SuccessReferenceRecord],
) -> str:
    reference_note = (
        f" Used {len(success_references)} success reference(s)." if success_references else ""
    )
    return f"Selected {len(selected)} bullet(s) by JD keyword overlap.{reference_note}"
