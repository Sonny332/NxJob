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

- AI or deterministic tailoring should produce structured resume content, selected bullet ids, warnings, layout budget, and quality checks.
- Local service owns file naming, directory validation, DOCX rendering, Markdown writing, caching, and ResumeVersion recording.
- Prompt logs must contain summaries and token usage only. Do not log full JD, full Master Resume, API key, or full prompt text.

