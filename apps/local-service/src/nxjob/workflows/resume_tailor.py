from __future__ import annotations

import re
import json
from dataclasses import dataclass
from math import ceil
from typing import Any

from pydantic import ValidationError

from nxjob.ai.openai_compatible import AiProviderError, request_json_object
from nxjob.schemas.core import (
    JobLeadRecord,
    MasterResumeEducation,
    MasterResumeBullet,
    MasterResumeExperience,
    SuccessReferenceRecord,
    TailoredResumeContent,
    TailoredExperienceSection,
)
from nxjob.settings.private_config import AiProviderConfig

WORKFLOW_NAME = "tailor_resume"
MAX_BODY_LINES = 55
TARGET_MIN_BODY_LINES = 52
NORMAL_LINE_CHARS = 118
BULLET_LINE_CHARS = 112

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
    experience: list[MasterResumeExperience] | None = None,
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
    experience_sections = _experience_sections(experience or [], jd_keywords, success_keywords)
    warnings = _quality_warnings(education_lines)
    content = TailoredResumeContent(
        candidate_name=candidate_name or "Candidate",
        contact_line=_fit_contact_line(contact_line),
        headline=headline,
        summary=summary,
        skills=skills,
        experience_sections=experience_sections,
        experience_bullets=[_fit_bullet_line(bullet.text) for bullet in selected],
        education=education_lines,
    )
    markdown = render_tailored_resume_markdown(content)
    layout_budget = estimate_layout_budget(content)
    quality_checks = {
        "one_page_budget_ok": layout_budget["body_lines"] <= MAX_BODY_LINES and layout_budget["heading_lines"] <= 5,
        "page_fill_target_met": layout_budget["body_lines"] >= TARGET_MIN_BODY_LINES,
        "contact_line_single_line": _line_count(content.contact_line, NORMAL_LINE_CHARS) <= 1,
        "education_years_present": bool(education_lines)
        and all(_contains_year_range(line) for line in education_lines),
        "summary_avoids_fixed_year_count": not any(re.search(r"\b\d+\+?\s+years?\b", line, re.I) for line in summary),
        "experience_timeline_preserved": _timeline_preserved(experience_sections),
        "renderer_uses_black_arial_template": True,
        "markdown_generated_from_same_content": True,
    }
    if not quality_checks["one_page_budget_ok"]:
        warnings.append("Estimated one-page layout budget is high; review DOCX before submitting.")
    if not quality_checks["page_fill_target_met"]:
        warnings.append("Estimated resume content is under the target page-fill budget; review for unused space.")
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


def tailor_resume_content_with_ai(
    job_lead: JobLeadRecord,
    bullets: list[MasterResumeBullet],
    success_references: list[SuccessReferenceRecord],
    ai_config: AiProviderConfig,
    candidate_name: str = "Candidate",
    contact_line: str = "",
    education: list[MasterResumeEducation] | None = None,
    experience: list[MasterResumeExperience] | None = None,
) -> TailorDraft:
    local_baseline = tailor_resume_content(
        job_lead,
        bullets,
        success_references,
        candidate_name=candidate_name,
        contact_line=contact_line,
        education=education,
        experience=experience,
    )
    result = request_json_object(
        ai_config,
        _ai_messages(
            job_lead,
            bullets,
            success_references,
            candidate_name=candidate_name,
            contact_line=contact_line,
            education=education or [],
            experience=experience or [],
            local_baseline=local_baseline,
        ),
    )
    return _draft_from_ai_payload(result.data, local_baseline, result.token_usage)


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


def _fit_bullet_line(text: str, target_chars: int = 128) -> str:
    compact = " ".join(text.split())
    if len(compact) <= target_chars:
        return compact
    clipped = compact[: target_chars - 1].rsplit(" ", 1)[0]
    return f"{clipped}."


def _experience_sections(
    experience: list[MasterResumeExperience],
    jd_keywords: list[str],
    success_keywords: list[str],
) -> list[TailoredExperienceSection]:
    sections: list[TailoredExperienceSection] = []
    for item in experience:
        ranked = sorted(
            item.bullets,
            key=lambda bullet: _bullet_score(bullet, jd_keywords, success_keywords),
            reverse=True,
        )
        selected = [bullet for bullet in ranked if _bullet_score(bullet, jd_keywords, success_keywords) > 0][:4]
        if not selected:
            selected = ranked[:1]
        date_range = _date_range(item.start_date, item.end_date)
        bullets = [_fit_bullet_line(bullet.text) for bullet in selected if bullet.text.strip()]
        if item.company.strip() or item.title.strip() or date_range or bullets:
            sections.append(
                TailoredExperienceSection(
                    company=item.company.strip(),
                    location=item.location.strip(),
                    title=item.title.strip(),
                    date_range=date_range,
                    bullets=bullets,
                )
            )
    return sections


def _date_range(start_date: str, end_date: str) -> str:
    start = start_date.strip()
    end = end_date.strip()
    if start and end:
        return f"{start} - {end}"
    return start or end


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
    normalized = line.replace("–", "-").replace("—", "-").replace("−", "-")
    return bool(re.search(r"\b(19|20)\d{2}\s*-\s*((19|20)\d{2}|Present)\b", normalized))


def _quality_warnings(education_lines: list[str]) -> list[str]:
    warnings: list[str] = []
    if not education_lines:
        warnings.append("Master Resume has no structured Education entries; add education years for stricter QA.")
    return warnings


def _timeline_preserved(sections: list[TailoredExperienceSection]) -> bool:
    return all(
        section.company.strip()
        and section.title.strip()
        and section.date_range.strip()
        and bool(section.bullets)
        for section in sections
    )


def estimate_layout_budget(content: TailoredResumeContent) -> dict[str, int]:
    heading_lines = 3
    if content.education:
        heading_lines += 1

    body_lines = 1
    if content.contact_line:
        body_lines += _line_count(content.contact_line, NORMAL_LINE_CHARS)
    body_lines += sum(_line_count(line, NORMAL_LINE_CHARS) for line in content.summary)
    body_lines += _line_count(", ".join(content.skills), NORMAL_LINE_CHARS) if content.skills else 0
    if content.experience_sections:
        for section in content.experience_sections:
            body_lines += _line_count(_experience_header_line(section), NORMAL_LINE_CHARS)
            body_lines += sum(_line_count(line, BULLET_LINE_CHARS) for line in section.bullets)
    else:
        body_lines += sum(_line_count(line, BULLET_LINE_CHARS) for line in content.experience_bullets)
    body_lines += sum(_line_count(line, NORMAL_LINE_CHARS) for line in content.education)

    return {
        "name_lines": 1,
        "heading_lines": heading_lines,
        "body_lines": body_lines,
        "max_heading_lines": 5,
        "max_body_lines": MAX_BODY_LINES,
        "target_min_body_lines": TARGET_MIN_BODY_LINES,
        "normal_line_chars": NORMAL_LINE_CHARS,
        "bullet_line_chars": BULLET_LINE_CHARS,
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

    if content.experience_sections:
        lines.extend(["", "## PROFESSIONAL EXPERIENCE"])
        for section in content.experience_sections:
            lines.append(f"**{_experience_header_line(section)}**")
            lines.extend(f"- {bullet}" for bullet in section.bullets)
    elif content.experience_bullets:
        lines.extend(["", "## PROFESSIONAL EXPERIENCE"])
        lines.extend(f"- {bullet}" for bullet in content.experience_bullets)

    if content.education:
        lines.extend(["", "## EDUCATION"])
        lines.extend(content.education)

    return "\n".join(lines).strip() + "\n"


def _experience_header_line(section: TailoredExperienceSection) -> str:
    role = " | ".join(part for part in [section.company, section.location] if part.strip())
    title = " | ".join(part for part in [section.title, section.date_range] if part.strip())
    if role and title:
        return f"{role} | {title}"
    return role or title


def _ai_messages(
    job_lead: JobLeadRecord,
    bullets: list[MasterResumeBullet],
    success_references: list[SuccessReferenceRecord],
    candidate_name: str,
    contact_line: str,
    education: list[MasterResumeEducation],
    experience: list[MasterResumeExperience],
    local_baseline: TailorDraft,
) -> list[dict[str, str]]:
    system = (
        "You are NxJob Resume Tailor. Return only a JSON object. "
        "Create a truthful, ATS-friendly, one-page English resume draft from the supplied JD "
        "and master resume evidence. Do not invent unsupported facts. Do not remove known "
        "experience in a way that creates timeline gaps. Education must include years when "
        "provided. If exact years of experience cannot be calculated reliably, do not state a "
        "numeric year count. Keep bullets dense for a one-page Arial DOCX renderer. "
        "Target 52-55 estimated body lines so the page is close to full without "
        "overflowing. Contact information must be one line; omit optional "
        "work-authorization or relocation wording from the contact line if needed. "
        "Experience bullets should usually land near a full line of text, roughly "
        "100-128 characters, and may use two lines only when the extra detail "
        "materially improves job match."
    )
    user = {
        "output_schema": {
            "content": {
                "candidate_name": "string",
                "contact_line": "string",
                "headline": "string",
                "summary": ["string"],
                "skills": ["string"],
                "experience_sections": [
                    {
                        "company": "string",
                        "location": "string",
                        "title": "string",
                        "date_range": "string",
                        "bullets": ["string"],
                    }
                ],
                "experience_bullets": ["string"],
                "education": ["string"],
            },
            "selected_bullet_ids": ["string"],
            "change_summary": "string",
            "layout_budget": {
                "name_lines": 1,
                "heading_lines": "integer <= 5",
                "body_lines": "integer <= 55",
                "max_heading_lines": 5,
                "max_body_lines": 55,
                "normal_line_chars": 118,
                "bullet_line_chars": 112,
            },
            "quality_checks": {
                "one_page_budget_ok": "boolean",
                "education_years_present": "boolean",
                "summary_avoids_fixed_year_count": "boolean",
                "truthful_to_master_resume": "boolean",
            },
            "warnings": ["string"],
        },
        "rendering_rules": {
            "font": "Arial",
            "colors": "black only",
            "page": "single column, one page target",
            "body_line_budget": 55,
            "target_body_lines": "52-55",
            "normal_line_chars": "110-118",
            "bullet_line_chars": "100-128 preferred; estimate wraps at 112",
            "contact_line": "single line only; keep location, phone, email, LinkedIn; omit optional status text if needed",
        },
        "job": {
            "company_name": job_lead.company_name,
            "job_title": job_lead.job_title,
            "location": job_lead.location,
            "page_title": job_lead.page_title,
            "jd_text": job_lead.jd_text[:12000],
        },
        "candidate": {
            "candidate_name": candidate_name,
            "contact_line": contact_line,
            "education": [item.model_dump() for item in education],
            "experience": [item.model_dump() for item in experience],
            "master_bullets": [bullet.model_dump() for bullet in bullets],
        },
        "success_references": [
            {
                "id": reference.id,
                "effective_keywords": reference.effective_keywords,
                "effective_bullets": reference.effective_bullets,
            }
            for reference in success_references
        ],
        "local_baseline": {
            "selected_bullet_ids": local_baseline.selected_bullet_ids,
            "experience_sections": [
                section.model_dump() for section in local_baseline.content.experience_sections
            ],
            "layout_budget": local_baseline.layout_budget,
            "quality_checks": local_baseline.quality_checks,
        },
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": _compact_json(user)},
    ]


def _draft_from_ai_payload(
    payload: dict[str, Any],
    local_baseline: TailorDraft,
    token_usage: dict[str, Any],
) -> TailorDraft:
    raw_content = payload.get("content", {})
    if not isinstance(raw_content, dict) or not _has_substantive_ai_payload(raw_content):
        raise AiProviderError(
            "invalid_response",
            "AI resume content was incomplete. Retry or switch provider.",
            502,
        )
    try:
        content = TailoredResumeContent.model_validate(raw_content)
    except ValidationError as exc:
        raise AiProviderError("invalid_response", "AI resume content did not match the expected schema.") from exc

    fit_warnings: list[str]
    content, repair_warnings = _repair_incomplete_ai_content(content, local_baseline)
    content, fit_warnings = _fit_content_to_one_page_budget(content, local_baseline)
    markdown = render_tailored_resume_markdown(content)
    layout_budget = estimate_layout_budget(content)
    selected_bullet_ids = [
        str(value)
        for value in payload.get("selected_bullet_ids", [])
        if isinstance(value, str) and value.strip()
    ]
    if not selected_bullet_ids:
        selected_bullet_ids = local_baseline.selected_bullet_ids

    warnings = [
        str(value)
        for value in payload.get("warnings", [])
        if isinstance(value, str) and value.strip()
    ]
    warnings.extend(repair_warnings)
    warnings.extend(fit_warnings)
    payload_quality_checks = payload.get("quality_checks")
    if not isinstance(payload_quality_checks, dict):
        payload_quality_checks = {}
    truthful_to_master_resume = bool(payload_quality_checks.get("truthful_to_master_resume", False))
    quality_checks = {
        "one_page_budget_ok": layout_budget["body_lines"] <= MAX_BODY_LINES and layout_budget["heading_lines"] <= 5,
        "page_fill_target_met": layout_budget["body_lines"] >= TARGET_MIN_BODY_LINES,
        "contact_line_single_line": _line_count(content.contact_line, NORMAL_LINE_CHARS) <= 1,
        "education_years_present": bool(content.education)
        and all(_contains_year_range(line) for line in content.education),
        "summary_avoids_fixed_year_count": not any(
            re.search(r"\b\d+\+?\s+years?\b", line, re.I) for line in content.summary
        ),
        "experience_timeline_preserved": _timeline_preserved(content.experience_sections),
        "truthful_to_master_resume": truthful_to_master_resume,
        "ai_repaired_from_baseline": bool(repair_warnings),
        "requires_user_review": bool(repair_warnings) or not truthful_to_master_resume,
        "renderer_uses_black_arial_template": True,
        "markdown_generated_from_same_content": True,
    }
    if not quality_checks["one_page_budget_ok"]:
        warnings.append("AI output is above the estimated one-page budget; review DOCX before submitting.")
    if not quality_checks["page_fill_target_met"]:
        warnings.append("AI output is below the target page-fill budget; review DOCX for unused space.")
    if not quality_checks["summary_avoids_fixed_year_count"]:
        warnings.append("AI output includes a numeric experience year count; verify the calculation.")
    if content.experience_sections and not quality_checks["experience_timeline_preserved"]:
        warnings.append("One or more experience sections are missing company, title, date range, or bullets.")

    return TailorDraft(
        content=content.model_copy(update={"markdown": markdown}),
        selected_bullet_ids=selected_bullet_ids,
        change_summary=str(payload.get("change_summary", "")).strip()
        or "Generated structured resume content with AI provider.",
        token_usage=token_usage,
        markdown=markdown,
        layout_budget=layout_budget,
        quality_checks=quality_checks,
        warnings=warnings,
    )


def _repair_incomplete_ai_content(
    content: TailoredResumeContent,
    baseline: TailorDraft,
) -> tuple[TailoredResumeContent, list[str]]:
    warnings: list[str] = []
    updates: dict[str, object] = {}
    baseline_content = baseline.content

    if _is_placeholder_candidate(content.candidate_name) and not _is_placeholder_candidate(
        baseline_content.candidate_name
    ):
        updates["candidate_name"] = baseline_content.candidate_name

    if not content.contact_line.strip() and baseline_content.contact_line.strip():
        updates["contact_line"] = baseline_content.contact_line

    if not content.summary and baseline_content.summary:
        updates["summary"] = baseline_content.summary

    if not content.skills and baseline_content.skills:
        updates["skills"] = baseline_content.skills

    has_experience = bool(content.experience_sections) or bool(content.experience_bullets)
    if not has_experience:
        if baseline_content.experience_sections:
            updates["experience_sections"] = baseline_content.experience_sections
        if baseline_content.experience_bullets:
            updates["experience_bullets"] = baseline_content.experience_bullets

    if not content.education and baseline_content.education:
        updates["education"] = baseline_content.education

    if updates:
        warnings.append("AI output was incomplete; filled missing resume sections from local baseline evidence.")
        content = content.model_copy(update=updates)

    if not _has_minimum_resume_content(content):
        raise AiProviderError(
            "invalid_response",
            "AI resume content was incomplete. Retry or switch provider.",
            502,
        )

    return content, warnings


def _has_substantive_ai_payload(raw_content: dict[str, Any]) -> bool:
    text_fields = [
        raw_content.get("contact_line"),
        raw_content.get("headline"),
    ]
    list_fields = [
        raw_content.get("summary"),
        raw_content.get("skills"),
        raw_content.get("experience_bullets"),
        raw_content.get("education"),
    ]
    if any(isinstance(value, str) and value.strip() for value in text_fields):
        return True
    if any(isinstance(value, list) and any(str(item).strip() for item in value) for value in list_fields):
        return True
    sections = raw_content.get("experience_sections")
    if isinstance(sections, list):
        for section in sections:
            if not isinstance(section, dict):
                continue
            bullets = section.get("bullets")
            section_text = " ".join(
                str(section.get(key, "")).strip()
                for key in ("company", "title", "date_range", "location")
            )
            if section_text.strip():
                return True
            if isinstance(bullets, list) and any(str(bullet).strip() for bullet in bullets):
                return True
    return False


def _is_placeholder_candidate(value: str) -> bool:
    return value.strip().lower() in {"", "candidate", "tailored resume"}


def _has_minimum_resume_content(content: TailoredResumeContent) -> bool:
    return bool(
        content.candidate_name.strip()
        and content.contact_line.strip()
        and content.summary
        and content.skills
        and (content.experience_sections or content.experience_bullets)
        and content.education
    )


def _fit_content_to_one_page_budget(
    content: TailoredResumeContent,
    baseline: TailorDraft | None = None,
) -> tuple[TailoredResumeContent, list[str]]:
    content = content.model_copy(update={"contact_line": _fit_contact_line(content.contact_line)})
    content, fill_warnings = _expand_underfilled_content(content, baseline)
    budget = estimate_layout_budget(content)
    if budget["body_lines"] <= MAX_BODY_LINES and budget["heading_lines"] <= 5:
        return content, fill_warnings

    warnings: list[str] = [*fill_warnings]
    adjusted = content

    if len(adjusted.skills) > 18:
        adjusted = adjusted.model_copy(update={"skills": adjusted.skills[:18]})
        warnings.append("Trimmed skill keywords to reduce one-page overflow risk.")

    sections = list(adjusted.experience_sections)
    removed_bullets = 0
    while sections and estimate_layout_budget(adjusted)["body_lines"] > MAX_BODY_LINES:
        changed = False
        for index in range(len(sections) - 1, -1, -1):
            section = sections[index]
            if len(section.bullets) <= 1:
                continue
            sections[index] = section.model_copy(update={"bullets": section.bullets[:-1]})
            adjusted = adjusted.model_copy(update={"experience_sections": sections})
            removed_bullets += 1
            changed = True
            break
        if not changed:
            break

    if removed_bullets:
        warnings.append(
            f"Compressed {removed_bullets} lower-priority bullet(s) to fit the one-page budget."
        )

    return adjusted, warnings


def _fit_contact_line(contact_line: str) -> str:
    compact = re.sub(r"\s*\|\s*", " | ", " ".join(contact_line.split())).strip()
    if _line_count(compact, NORMAL_LINE_CHARS) <= 1:
        return compact

    parts = [part.strip() for part in compact.split("|") if part.strip()]
    contact_parts = [part for part in parts if _looks_like_core_contact_part(part)]
    if len(contact_parts) >= 3:
        candidate = " | ".join(contact_parts)
        if _line_count(candidate, NORMAL_LINE_CHARS) <= 1:
            return candidate

    condensed = " | ".join(parts[:4]) if len(parts) >= 4 else compact
    return condensed[:NORMAL_LINE_CHARS].rstrip(" |,;")


def _looks_like_core_contact_part(value: str) -> bool:
    lower = value.lower()
    return (
        "@" in value
        or "linkedin" in lower
        or bool(re.search(r"\d{3}[-.\s]\d{3}[-.\s]\d{4}", value))
        or lower.endswith(", ma")
        or "boston" in lower
    )


def _expand_underfilled_content(
    content: TailoredResumeContent,
    baseline: TailorDraft | None,
) -> tuple[TailoredResumeContent, list[str]]:
    if baseline is None or not content.experience_sections:
        return content, []
    if estimate_layout_budget(content)["body_lines"] >= TARGET_MIN_BODY_LINES:
        return content, []

    baseline_by_key = {_section_key(section): section for section in baseline.content.experience_sections}
    sections = list(content.experience_sections)
    added = 0
    changed = True
    while changed and estimate_layout_budget(content.model_copy(update={"experience_sections": sections}))[
        "body_lines"
    ] < TARGET_MIN_BODY_LINES:
        changed = False
        for index, section in enumerate(sections):
            baseline_section = baseline_by_key.get(_section_key(section))
            if baseline_section is None:
                continue
            existing = {_normalize_for_compare(bullet) for bullet in section.bullets}
            for candidate in baseline_section.bullets:
                fitted = _fit_bullet_line(candidate)
                if _normalize_for_compare(fitted) in existing:
                    continue
                candidate_sections = list(sections)
                candidate_sections[index] = section.model_copy(update={"bullets": [*section.bullets, fitted]})
                candidate_content = content.model_copy(update={"experience_sections": candidate_sections})
                if estimate_layout_budget(candidate_content)["body_lines"] > MAX_BODY_LINES:
                    continue
                sections = candidate_sections
                added += 1
                changed = True
                break
            if changed:
                break

    if not added:
        return content, []
    return content.model_copy(update={"experience_sections": sections}), [
        f"Added {added} truthful baseline bullet(s) to improve page fill."
    ]


def _section_key(section: TailoredExperienceSection) -> str:
    return "|".join(
        [
            section.company.strip().lower(),
            section.title.strip().lower(),
            section.date_range.strip().lower(),
        ]
    )


def _normalize_for_compare(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _compact_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
