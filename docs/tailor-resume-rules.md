# Tailor Resume Rules

M11 Tailor Resume generates an English, ATS-friendly, one-page-first resume from a captured JD and the local Master Resume.

## Output Contract

- Generate both `.docx` and matching `.md`.
- Use a user-configured resume output folder. Do not silently write generated resumes to a default C drive location.
- Default filename policy: `YYYY-MM-DD_<company>_<job-title>_resume`.
- Sanitize path characters and append `_v2`, `_v3`, and so on instead of overwriting existing files.

## Content Rules

- Use only evidence supported by the Master Resume or Success References.
- Do not invent certificates, ownership, commissioning authority, vendor-platform depth, budgets, savings, production volumes, team sizes, or other unsupported facts.
- Do not remove known work periods in a way that creates unexplained date gaps.
- When structured Master Resume `experience` entries are available, render professional experience by company/title/date section and keep each known role represented.
- Education must include years when structured education data is available.
- Summary must not use a fixed numeric years-of-experience claim unless the runtime can calculate it conservatively from structured work history.

## Layout Rules

- DOCX renderer uses Arial, pure black text and section rules, single column, and compact margins.
- Section headings use black bottom borders rather than typed divider characters.
- M11 uses a budget model before full document validation:
  - Name: 1 line.
  - Section headings: up to 5 lines.
  - Body: up to 55 estimated lines.
  - Normal text: 110-118 characters per line.
  - Bullet text: 105-112 characters per line.

## Architecture

- If an OpenAI-compatible provider is configured, AI tailoring produces structured resume content, selected bullet ids, warnings, layout budget, and quality checks.
- If no AI provider is configured, deterministic local tailoring remains available for development and offline smoke tests.
- Tailored content supports `experience_sections` for role-based rendering. Flat `experience_bullets` remain only as a backward-compatible fallback.
- Local service owns file naming, directory validation, DOCX rendering, Markdown writing, caching, and ResumeVersion recording.
- AI output with no substantive resume content must fail with a plugin-readable `invalid_response` error. Do not create DOCX/Markdown artifacts, `ResumeVersion`, or a `tailored` JobLead status from an empty provider response.
- Provider errors must be categorized into plugin-readable messages without echoing provider response bodies that could contain sensitive request data.
- Prompt logs must contain summaries, provider/model labels, sanitized error categories, and token usage only. Do not log full JD, full Master Resume, API key, or full prompt text.

