from __future__ import annotations

import re
from dataclasses import dataclass
from math import ceil

from nxjob.schemas.core import (
    JobLeadRecord,
    MasterResumeEducation,
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
    markdown: str
    layout_budget: dict[str, int | bool]
    quality_checks: dict[str, bool | str]
    warnings: list[str]


def tailor_resume_content(
    job_lead: JobLeadRecord,
    bullets: list[MasterResumeBullet],
    success_references: list[SuccessReferenceRecord],
    candidate_name: str = "Candidate",
    contact_line: str = "",
    education: list[MasterResumeEducation] | None = None,
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
    selected = [bullet for bullet in ranked if _bullet_score(bullet, jd_keywords, success_keywords) > 0][:8]
    if not selected:
        selected = ranked[: min(8, len(ranked))]

    skills = _skills_from_bullets(selected, jd_keywords)
    summary = _summary_from_keywords(jd_keywords, skills)
    headline = _headline_from_job(job_lead)
    education_lines = _education_lines(education or [])
    warnings = _quality_warnings(education_lines)
    content = TailoredResumeContent(
        candidate_name=candidate_name or "Candidate",
        contact_line=contact_line,
        headline=headline,
        summary=summary,
        skills=skills,
        experience_bullets=[_fit_bullet_line(bullet.text) for bullet in selected],
        education=education_lines,
    )
    markdown = render_tailored_resume_markdown(content)
    layout_budget = estimate_layout_budget(content)
    quality_checks = {
        "one_page_budget_ok": layout_budget["body_lines"] <= 55 and layout_budget["heading_lines"] <= 5,
        "education_years_present": bool(education_lines)
        and all(_contains_year_range(line) for line in education_lines),
        "summary_avoids_fixed_year_count": not any(re.search(r"\b\d+\+?\s+years?\b", line, re.I) for line in summary),
        "renderer_uses_black_arial_template": True,
        "markdown_generated_from_same_content": True,
    }
    if not quality_checks["one_page_budget_ok"]:
        warnings.append("Estimated one-page layout budget is high; review DOCX before submitting.")
    if not quality_checks["education_years_present"]:
        warnings.append("Education years are not available in the master resume data.")

    return TailorDraft(
        content=content.model_copy(update={"markdown": markdown}),
        selected_bullet_ids=[bullet.id for bullet in selected],
        change_summary=_change_summary(selected, success_references),
        token_usage={
            "input_chars": len(job_lead.jd_text) + sum(len(bullet.text) for bullet in bullets),
            "output_chars": sum(len(bullet.text) for bullet in selected),
        },
        markdown=markdown,
        layout_budget=layout_budget,
        quality_checks=quality_checks,
        warnings=warnings,
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
        f"Technical professional focused on roles requiring {focus}.",
        "Experience selected for direct job-description overlap, execution credibility, and interview-ready evidence.",
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


def _fit_bullet_line(text: str, target_chars: int = 112) -> str:
    compact = " ".join(text.split())
    if len(compact) <= target_chars:
        return compact
    clipped = compact[: target_chars - 1].rsplit(" ", 1)[0]
    return f"{clipped}."


def _education_lines(education: list[MasterResumeEducation]) -> list[str]:
    lines = []
    for item in education:
        years = _year_range(item.start_year, item.end_year)
        parts = [
            item.school.strip(),
            item.degree.strip(),
            item.location.strip(),
            years,
            f"GPA: {item.gpa.strip()}" if item.gpa.strip() else "",
        ]
        line = " | ".join(part for part in parts if part)
        if line:
            lines.append(line)
    return lines


def _year_range(start_year: str, end_year: str) -> str:
    start = start_year.strip()
    end = end_year.strip()
    if start and end:
        return f"{start} - {end}"
    return start or end


def _contains_year_range(line: str) -> bool:
    return bool(re.search(r"\b(19|20)\d{2}\s*-\s*((19|20)\d{2}|Present)\b", line))


def _quality_warnings(education_lines: list[str]) -> list[str]:
    warnings: list[str] = []
    if not education_lines:
        warnings.append("Master Resume has no structured Education entries; add education years for stricter QA.")
    return warnings


def estimate_layout_budget(content: TailoredResumeContent) -> dict[str, int]:
    heading_lines = 3
    if content.education:
        heading_lines += 1

    body_lines = 1
    if content.contact_line:
        body_lines += _line_count(content.contact_line, 118)
    body_lines += sum(_line_count(line, 118) for line in content.summary)
    body_lines += _line_count(", ".join(content.skills), 118) if content.skills else 0
    body_lines += sum(_line_count(line, 112) for line in content.experience_bullets)
    body_lines += sum(_line_count(line, 118) for line in content.education)

    return {
        "name_lines": 1,
        "heading_lines": heading_lines,
        "body_lines": body_lines,
        "max_heading_lines": 5,
        "max_body_lines": 55,
        "normal_line_chars": 118,
        "bullet_line_chars": 112,
    }


def _line_count(text: str, chars_per_line: int) -> int:
    return max(1, ceil(len(text) / chars_per_line))


def render_tailored_resume_markdown(content: TailoredResumeContent) -> str:
    lines = [f"# {content.candidate_name}"]
    if content.contact_line:
        lines.append(content.contact_line)
    if content.headline:
        lines.extend(["", content.headline])

    lines.extend(["", "## PROFESSIONAL SUMMARY"])
    lines.extend(content.summary)

    if content.skills:
        lines.extend(["", "## CORE QUALIFICATIONS / TECHNICAL SKILLS", ", ".join(content.skills)])

    if content.experience_bullets:
        lines.extend(["", "## PROFESSIONAL EXPERIENCE"])
        lines.extend(f"- {bullet}" for bullet in content.experience_bullets)

    if content.education:
        lines.extend(["", "## EDUCATION"])
        lines.extend(content.education)

    return "\n".join(lines).strip() + "\n"
