from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from nxjob.ai.openai_compatible import AiProviderError, request_json_object
from nxjob.schemas.core import FieldContext, JobLeadRecord, MasterResumeBullet, MasterResumeProfile
from nxjob.settings.private_config import AiProviderConfig
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
    ai_config: AiProviderConfig | None = None,
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
    if ai_config is not None:
        try:
            return _draft_with_ai(job_lead, field_context, selected, ai_config)
        except AiProviderError as exc:
            fallback = _draft_open_answer(field_context, selected)
            return FormAnswerDraft(
                answer=fallback,
                referenced_bullets=[bullet.id for bullet in selected],
                risk_flags=[
                    f"AI provider unavailable: {exc.category}. Review carefully before filling.",
                    "Local fallback may be less specific to the form question.",
                ],
                ai_used=False,
                token_usage={"input_chars": len(job_lead.jd_text) + len(field_text), "output_chars": len(fallback)},
            )

    answer = _draft_open_answer(field_text, selected)
    risk_flags = ["User review required before filling or submitting."]
    if not selected:
        risk_flags.append("No matching resume bullet was found.")
    if _is_choice_field(field_context):
        risk_flags.append("No AI provider configured; choice fields may require manual selection.")

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


def _draft_with_ai(
    job_lead: JobLeadRecord,
    field_context: FieldContext,
    selected: list[MasterResumeBullet],
    ai_config: AiProviderConfig,
) -> FormAnswerDraft:
    result = request_json_object(ai_config, _ai_messages(job_lead, field_context, selected), timeout_seconds=45)
    answer = _clean_string(result.data.get("answer"))
    if not answer:
        raise AiProviderError("invalid_response", "AI provider did not return a form answer.")

    risk_flags = _string_list(result.data.get("risk_flags"))
    referenced = [
        bullet_id
        for bullet_id in _string_list(result.data.get("referenced_bullets"))
        if any(bullet.id == bullet_id for bullet in selected)
    ]

    if _is_choice_field(field_context):
        matched = _match_option(answer, field_context.options)
        if matched is None:
            matched = _match_option(_clean_string(result.data.get("option")), field_context.options)
        if matched is None:
            fallback = _draft_open_answer(field_context, selected)
            return FormAnswerDraft(
                answer=fallback,
                referenced_bullets=referenced or [bullet.id for bullet in selected],
                risk_flags=[
                    "AI answer did not match an available form option. Select manually.",
                    *risk_flags,
                ],
                ai_used=True,
                token_usage=_token_usage(result.token_usage),
            )
        answer = matched

    return FormAnswerDraft(
        answer=answer,
        referenced_bullets=referenced or [bullet.id for bullet in selected],
        risk_flags=risk_flags or ["User review required before filling or submitting."],
        ai_used=True,
        token_usage=_token_usage(result.token_usage),
    )


def _ai_messages(
    job_lead: JobLeadRecord,
    field_context: FieldContext,
    selected: list[MasterResumeBullet],
) -> list[dict[str, str]]:
    system = (
        "You are NxJob Form Answer Drafter. Return only a JSON object. "
        "Answer the specific application form field, not a generic resume summary. "
        "Use only supplied resume evidence and stable facts. Do not invent credentials, dates, "
        "immigration facts, metrics, employers, or personal data. Keep answers concise. "
        "If options are supplied for a select, radio, or checkbox field, choose exactly one supplied option "
        "when possible. Never claim that the application was submitted."
    )
    user = {
        "field": {
            "label": field_context.label,
            "placeholder": field_context.placeholder,
            "surrounding_text": field_context.surrounding_text[:1000],
            "input_type": field_context.input_type,
            "required": field_context.required,
            "options": field_context.options[:30],
        },
        "job": {
            "title": job_lead.job_title,
            "company": job_lead.company_name,
            "keywords": extract_keywords(job_lead.jd_text, limit=24),
        },
        "resume_evidence": [
            {"id": bullet.id, "text": bullet.text, "tags": bullet.tags}
            for bullet in selected[:5]
        ],
        "required_json": {
            "answer": "string; for choice fields use the exact matching option text",
            "option": "string; exact option text when choosing from options, otherwise empty",
            "referenced_bullets": ["bullet_id"],
            "risk_flags": ["short review warning if needed"],
        },
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user, ensure_ascii=False, separators=(",", ":"))},
    ]


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


def _draft_open_answer(field_context: FieldContext | str, selected: list[MasterResumeBullet]) -> str:
    field_text = _field_text(field_context) if isinstance(field_context, FieldContext) else field_context
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


def _is_choice_field(field_context: FieldContext) -> bool:
    value = field_context.input_type.strip().lower()
    return value in {"select", "radio", "checkbox"} or bool(field_context.options)


def _match_option(answer: str, options: list[str]) -> str | None:
    clean_answer = answer.strip().lower()
    if not clean_answer or not options:
        return None
    for option in options:
        if option.strip().lower() == clean_answer:
            return option
    for option in options:
        clean_option = option.strip().lower()
        if clean_option and clean_option in clean_answer:
            return option
    return None


def _clean_string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _token_usage(value: dict[str, Any]) -> dict[str, int]:
    usage: dict[str, int] = {}
    for key, raw_value in value.items():
        if isinstance(raw_value, int):
            usage[key] = raw_value
    return usage
