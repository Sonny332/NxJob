from __future__ import annotations

from dataclasses import dataclass

from nxjob.schemas.core import FieldContext, JobLeadRecord, MasterResumeBullet, MasterResumeProfile
from nxjob.workflows.resume_tailor import extract_keywords

WORKFLOW_NAME = "draft_form_answer_from_resume_bullets"


@dataclass(frozen=True)
class FormAnswerDraft:
    answer: str
    referenced_bullets: list[str]
    risk_flags: list[str]
    ai_used: bool
    token_usage: dict[str, int]


def draft_form_answer(
    job_lead: JobLeadRecord,
    field_context: FieldContext,
    master_resume: MasterResumeProfile,
    request_bullets: list[MasterResumeBullet],
) -> FormAnswerDraft:
    field_text = _field_text(field_context)
    fixed_answer = _fixed_answer(field_text, master_resume.fixed_answers)
    if fixed_answer is not None:
        return FormAnswerDraft(
            answer=fixed_answer,
            referenced_bullets=[],
            risk_flags=[],
            ai_used=False,
            token_usage={"input_chars": len(field_text), "output_chars": len(fixed_answer)},
        )

    bullets = request_bullets or master_resume.bullets
    selected = _select_bullets(job_lead.jd_text, field_text, bullets)
    answer = _draft_open_answer(field_text, selected)
    risk_flags = ["User review required before filling or submitting."]
    if not selected:
        risk_flags.append("No matching resume bullet was found.")

    return FormAnswerDraft(
        answer=answer,
        referenced_bullets=[bullet.id for bullet in selected],
        risk_flags=risk_flags,
        ai_used=True,
        token_usage={
            "input_chars": len(job_lead.jd_text) + len(field_text) + sum(len(bullet.text) for bullet in bullets),
            "output_chars": len(answer),
        },
    )


def _field_text(field_context: FieldContext) -> str:
    return " ".join(
        value.strip()
        for value in [
            field_context.label,
            field_context.placeholder,
            field_context.surrounding_text,
            field_context.input_type,
        ]
        if value.strip()
    ).lower()


def _fixed_answer(field_text: str, fixed_answers: dict[str, str]) -> str | None:
    for key, value in fixed_answers.items():
        normalized = key.strip().lower()
        if normalized and normalized in field_text:
            return value

    common_keys = {
        "email": ["email", "e-mail"],
        "phone": ["phone", "mobile", "telephone"],
        "current location": ["location", "city", "address"],
        "work authorization": ["work authorization", "authorized to work"],
        "sponsorship": ["sponsorship", "visa"],
    }
    for answer_key, patterns in common_keys.items():
        if answer_key in fixed_answers and any(pattern in field_text for pattern in patterns):
            return fixed_answers[answer_key]
    return None


def _select_bullets(
    jd_text: str,
    field_text: str,
    bullets: list[MasterResumeBullet],
) -> list[MasterResumeBullet]:
    keywords = [*extract_keywords(jd_text, limit=16), *extract_keywords(field_text, limit=8)]

    def score(bullet: MasterResumeBullet) -> int:
        text = f"{bullet.text} {' '.join(bullet.tags)}".lower()
        return sum(1 for keyword in keywords if keyword in text)

    ranked = sorted(bullets, key=score, reverse=True)
    return [bullet for bullet in ranked if score(bullet) > 0][:3]


def _draft_open_answer(field_text: str, selected: list[MasterResumeBullet]) -> str:
    if not selected:
        return "I have relevant experience for this role and can provide more detail during the interview process."

    if "why" in field_text or "interest" in field_text:
        return (
            "I am interested in this role because it aligns with my experience in "
            f"{_compact_bullet_phrase(selected[0])}."
        )

    joined = " ".join(_compact_bullet_phrase(bullet) for bullet in selected)
    return f"My relevant experience includes {joined}"


def _compact_bullet_phrase(bullet: MasterResumeBullet) -> str:
    text = bullet.text.strip().rstrip(".")
    return text[:260] + ("..." if len(text) > 260 else ".")
