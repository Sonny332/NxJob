# Master Resume Builder Plan

## Decision

NxJob runtime uses one canonical master resume format: validated local JSON.

MVP should not directly run tailoring workflows against `.md`, `.txt`, `.doc`, or `.docx` resume sources. Those files may be used later as import sources, but they must be converted into the NxJob JSON format before the local service uses them.

## Why

Resume tailoring and form-answer drafting depend on stable, reusable bullets. The runtime needs predictable fields:

- `candidate_name`
- `contact_line`
- `bullets[].id`
- `bullets[].text`
- `bullets[].tags`
- `fixed_answers`

Free-form resumes are useful as source material, but they are not reliable runtime input. Headings, bullet boundaries, project grouping, skills, and personal facts vary too much across resume formats.

## Current MVP Flow

1. User starts with an existing resume.
2. User uses a provided prompt in ChatGPT, Claude, Gemini, or another LLM.
3. The LLM converts the existing resume into NxJob Master Resume JSON.
4. User reviews the generated JSON.
5. User saves the JSON through the plugin setup UI or local private config.
6. NxJob validates the JSON before using it.

The current runtime remains JSON-only.

## Future Skill: `build_master_resume`

The future skill should accept resume source material and produce validated NxJob Master Resume JSON.

Inputs:

- Pasted resume text.
- Uploaded `.txt` or `.md`.
- Uploaded `.docx` after text extraction.
- Optional user notes about target roles.
- Optional fixed answers for forms.

Outputs:

- `MasterResumeProfile` JSON.
- Validation warnings.
- Missing-information questions.
- A short change summary.

Rules:

- Do not invent work history, credentials, schools, dates, or metrics.
- Rewrite for clarity only when the source supports it.
- Split long resume content into reusable evidence bullets.
- Generate stable, descriptive bullet ids.
- Add concise tags that help JD matching.
- Put stable personal facts in `fixed_answers`.
- Do not store secrets such as API keys, passwords, SSNs, or full immigration documents.

## Future User Flow

User layer:

- Upload Resume Source.
- Paste Resume Text.
- Build Master Resume.
- Review JSON.
- Save to private config.

Local runtime layer:

- Extract text from source files.
- Call the AI conversion workflow.
- Validate JSON against the schema.
- Save only validated output for runtime use.
- Keep private files outside Git.

AI layer:

- Structure existing facts.
- Convert resume content into reusable bullets.
- Generate tags.
- Extract fixed answers.
- Identify ambiguous or missing facts.

## Privacy Boundary

Uploaded resume sources and generated JSON are private user data.

Default behavior:

- Store generated JSON under local private config.
- Do not commit generated JSON.
- Do not include generated JSON in release packages.
- Do not write full resume source text into normal logs.
- Do not write API keys or secrets into prompt logs.

For future import sources, NxJob should either:

- Not persist the raw source file after conversion, or
- Store it under a local private import directory with a clear delete option.

## Builder Prompt Template

Use this prompt outside NxJob until the in-app skill exists:

```text
You are converting my existing resume into the NxJob Master Resume JSON format.

Rules:
- Output valid JSON only. Do not include Markdown fences.
- Do not invent employers, titles, dates, schools, credentials, metrics, or tools.
- If a fact is unclear, omit it or add a short note in a tag such as "needs_review".
- Convert resume experience into reusable evidence bullets.
- Each bullet must have:
  - a stable snake_case id
  - a concise evidence-based text
  - tags for technologies, skills, domains, and role keywords
- Put stable form answers in fixed_answers when clearly present.
- Do not include secrets, SSNs, passwords, or full immigration documents.

Required JSON shape:
{
  "id": "master_default",
  "candidate_name": "",
  "contact_line": "",
  "bullets": [
    {
      "id": "example_bullet_01",
      "text": "Evidence-based resume bullet.",
      "tags": ["Skill", "Tool", "Domain"]
    }
  ],
  "fixed_answers": {
    "email": "",
    "phone": "",
    "current location": "",
    "work authorization": ""
  }
}

Existing resume source:
[PASTE RESUME HERE]
```

## Acceptance Criteria

MVP documentation is complete when:

- `docs/master-resume-format.md` states JSON is the only runtime format.
- This plan explains the future import/build workflow.
- Privacy rules are aligned with `docs/privacy-boundary.md`.

Future implementation is complete when:

- A user can provide `.txt`, `.md`, or `.docx` source material.
- NxJob converts it into validated JSON.
- The user can review before saving.
- Runtime workflows still load only validated JSON.
