from __future__ import annotations

import json
import re
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
    question_text: str = ""
    intent: str = "custom"
    answer_type: str = "text"
    confidence: float = 0.0
    selected_option: str = ""
    evidence_summary: list[str] | None = None


def draft_form_answer(
    job_lead: JobLeadRecord,
    field_context: FieldContext,
    master_resume: MasterResumeProfile,
    request_bullets: list[MasterResumeBullet],
    ai_config: AiProviderConfig | None = None,
) -> FormAnswerDraft:
    field_text = _field_text(field_context)
    question_text = _question_text(field_context)
    intent = _classify_intent(field_context)
    answer_type = _answer_type(field_context)
    fixed_answer = _fixed_answer(field_context, master_resume.fixed_answers)
    if fixed_answer is not None:
        return FormAnswerDraft(
            answer=fixed_answer,
            referenced_bullets=[],
            risk_flags=[],
            ai_used=False,
            token_usage={"input_chars": len(field_text), "output_chars": len(fixed_answer)},
            question_text=question_text,
            intent=intent,
            answer_type=answer_type,
            confidence=0.95,
            selected_option=fixed_answer if _is_choice_field(field_context) else "",
        )

    bullets = request_bullets or master_resume.bullets
    selected = _select_bullets(job_lead.jd_text, field_text, bullets)
    if intent == "salary":
        answer = "I am open to discussing compensation based on the role scope, total package, and market range."
        return FormAnswerDraft(
            answer=answer,
            referenced_bullets=[],
            risk_flags=["Salary answer requires manual review before filling."],
            ai_used=False,
            token_usage={"input_chars": len(field_text), "output_chars": len(answer)},
            question_text=question_text,
            intent=intent,
            answer_type=answer_type,
            confidence=0.7,
        )
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
                question_text=question_text,
                intent=intent,
                answer_type=answer_type,
                confidence=0.45,
                evidence_summary=[bullet.text for bullet in selected[:2]],
            )

    answer = _draft_open_answer(field_text, selected)
    risk_flags = ["Manual review required before filling or submitting."]
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
        question_text=question_text,
        intent=intent,
        answer_type=answer_type,
        confidence=0.55 if selected else 0.3,
        evidence_summary=[bullet.text for bullet in selected[:2]],
    )


def _field_text(field_context: FieldContext) -> str:
    return " ".join(
        value.strip()
        for value in [
            field_context.label,
            field_context.question_text,
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
    question_text = _clean_string(result.data.get("question_text")) or _question_text(field_context)
    intent = _clean_string(result.data.get("intent")) or _classify_intent(field_context)
    answer_type = _clean_string(result.data.get("answer_type")) or _answer_type(field_context)
    answer = _clean_string(result.data.get("answer"))
    if not answer:
        raise AiProviderError("invalid_response", "AI provider did not return a form answer.")

    risk_flags = _string_list(result.data.get("risk_flags"))
    confidence = _confidence(result.data.get("confidence"), 0.75)
    referenced = [
        bullet_id
        for bullet_id in _string_list(result.data.get("referenced_bullets"))
        if any(bullet.id == bullet_id for bullet in selected)
    ]
    selected_option = ""

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
                question_text=question_text,
                intent=intent,
                answer_type=answer_type,
                confidence=min(confidence, 0.35),
                evidence_summary=[bullet.text for bullet in selected[:2]],
            )
        answer = matched
        selected_option = matched

    return FormAnswerDraft(
        answer=answer,
        referenced_bullets=referenced or [bullet.id for bullet in selected],
        risk_flags=risk_flags or ["User review required before filling or submitting."],
        ai_used=True,
        token_usage=_token_usage(result.token_usage),
        question_text=question_text,
        intent=intent,
        answer_type=answer_type,
        confidence=confidence,
        selected_option=selected_option,
        evidence_summary=[bullet.text for bullet in selected[:2]],
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
            "question_text": _question_text(field_context),
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
            "question_text": "string; the form question being answered",
            "intent": "one of fixed_personal_fact, work_authorization, sponsorship, relocation, availability, salary, why_fit, motivation, experience, skills, custom",
            "answer_type": "text, single_choice, multi_choice, boolean, date, number",
            "answer": "string; for choice fields use the exact matching option text",
            "option": "string; exact option text when choosing from options, otherwise empty",
            "confidence": "number between 0 and 1",
            "referenced_bullets": ["bullet_id"],
            "risk_flags": ["short review warning if needed"],
        },
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user, ensure_ascii=False, separators=(",", ":"))},
    ]


def _fixed_answer(field_context: FieldContext, fixed_answers: dict[str, str]) -> str | None:
    field_text = _field_text(field_context)
    for answer_key, patterns in _simple_fixed_answer_patterns().items():
        value = _lookup_fixed_answer(fixed_answers, answer_key)
        if value and any(pattern in field_text for pattern in patterns):
            return value

    sponsorship_fact = _lookup_fixed_answer(fixed_answers, "sponsorship") or _lookup_fixed_answer(
        fixed_answers,
        "work authorization",
    )
    if sponsorship_fact and _asks_sponsorship(field_text):
        if _is_choice_field(field_context):
            return _choice_from_sponsorship_fact(sponsorship_fact, field_context.options)
        return sponsorship_fact

    authorization_fact = _lookup_fixed_answer(fixed_answers, "authorized to work") or _lookup_fixed_answer(
        fixed_answers,
        "work authorized",
    )
    if authorization_fact and _asks_work_authorization(field_text):
        if _is_choice_field(field_context):
            return _choice_from_authorization_fact(authorization_fact, field_context.options)
        return authorization_fact

    return None


def _simple_fixed_answer_patterns() -> dict[str, list[str]]:
    return {
        "email": ["email", "e-mail"],
        "phone": ["phone", "mobile", "telephone"],
        "current location": ["current location", "location", "city", "address"],
        "linkedin": ["linkedin"],
        "portfolio": ["portfolio", "website"],
    }


def _lookup_fixed_answer(fixed_answers: dict[str, str], key: str) -> str:
    for raw_key, value in fixed_answers.items():
        if raw_key.strip().lower() == key and value.strip():
            return value
    return ""


def _asks_sponsorship(field_text: str) -> bool:
    return any(term in field_text for term in ["sponsorship", "visa sponsor", "visa sponsorship", "h-1b", "h1b"])


def _asks_work_authorization(field_text: str) -> bool:
    return any(term in field_text for term in ["authorized to work", "work authorization", "legally authorized"])


def _choice_from_sponsorship_fact(fact: str, options: list[str]) -> str | None:
    lower_fact = fact.lower()
    if (
        any(
            term in lower_fact
            for term in [
                "do not require",
                "does not require",
                "will not require",
                "not require",
                "do not need",
                "does not need",
                "will not need",
                "not need",
                "no sponsorship",
            ]
        )
        or _has_word(lower_fact, "no")
    ):
        return _match_option("No", options)
    if any(term in lower_fact for term in ["require", "requires", "need", "needs", "yes"]):
        return _match_option("Yes", options)
    return None


def _choice_from_authorization_fact(fact: str, options: list[str]) -> str | None:
    lower_fact = fact.lower()
    if any(term in lower_fact for term in ["not authorized", "not legally authorized"]):
        return _match_option("No", options)
    if any(term in lower_fact for term in ["authorized", "legally authorized", "yes"]):
        return _match_option("Yes", options)
    return None


def _has_word(text: str, word: str) -> bool:
    return re.search(rf"\b{re.escape(word)}\b", text) is not None


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


def _question_text(field_context: FieldContext) -> str:
    for value in [field_context.question_text, field_context.label, field_context.placeholder]:
        if value.strip():
            return value.strip()
    text = field_context.surrounding_text.strip()
    if not text:
        return ""
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    return first_line[:240]


def _classify_intent(field_context: FieldContext) -> str:
    field_text = _field_text(field_context)
    if _asks_sponsorship(field_text):
        return "sponsorship"
    if _asks_work_authorization(field_text):
        return "work_authorization"
    if any(term in field_text for term in ["salary", "compensation", "pay expectation", "desired pay"]):
        return "salary"
    if any(term in field_text for term in ["relocat", "commute", "location", "hybrid", "remote", "onsite", "on-site"]):
        return "relocation"
    if any(term in field_text for term in ["available", "start date", "notice period"]):
        return "availability"
    if "why" in field_text and any(term in field_text for term in ["fit", "qualified", "good candidate", "best candidate"]):
        return "why_fit"
    if any(term in field_text for term in ["interest", "motivation", "why do you want"]):
        return "motivation"
    if any(term in field_text for term in ["experience", "describe", "tell us about"]):
        return "experience"
    if any(term in field_text for term in ["skill", "tool", "software", "proficient"]):
        return "skills"
    if any(term in field_text for term in ["email", "phone", "linkedin", "portfolio", "address"]):
        return "fixed_personal_fact"
    return "custom"


def _answer_type(field_context: FieldContext) -> str:
    input_type = field_context.input_type.strip().lower()
    if input_type in {"select", "radio"}:
        return "single_choice"
    if input_type == "checkbox":
        return "multi_choice" if len(field_context.options) > 1 else "boolean"
    if input_type in {"number", "tel"}:
        return "number" if input_type == "number" else "text"
    if input_type in {"date", "datetime-local", "month"}:
        return "date"
    return "text"


def _confidence(value: Any, default: float) -> float:
    if isinstance(value, int | float):
        return max(0.0, min(1.0, float(value)))
    return default


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
