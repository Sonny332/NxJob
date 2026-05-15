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
You are helping me convert an existing resume into NxJob Master Resume JSON.

NxJob uses this JSON as a private local source book for resume tailoring and form-answer drafting. Your job is to preserve truthful, interview-defensible facts and structure them so software can reliably select relevant evidence.

Important workflow:
1. First read my existing resume source.
2. Do not immediately output JSON if important facts are missing or ambiguous.
3. Ask me only the necessary follow-up questions needed to produce reliable JSON.
4. After I answer, output valid JSON only. Do not include Markdown fences or commentary.

Do not invent:
- employers
- titles
- dates
- schools
- degrees
- credentials
- project metrics
- budget, cost, team-size, production, savings, or performance numbers
- software/tool proficiency levels
- immigration or work-authorization facts not explicitly provided

Privacy and safety rules:
- Do not include API keys, passwords, SSNs, full immigration documents, identity document numbers, or bank/tax details.
- If a sensitive form answer is unclear, omit it instead of guessing.
- If a fact is unclear but useful, either ask me a follow-up question or tag the related bullet with "needs_review".
- Preserve the full known work and education timeline. Do not remove a role just because it seems less relevant.

Questions to ask before JSON if missing:
- Preferred display name and one-line contact information.
- Target role families or job categories.
- Complete work timeline with company, title, location, start/end date, and current employer.
- For each role, 3-8 evidence-based bullets with tools, systems, responsibilities, business context, and supported results.
- Education years, degree names, schools, locations, and GPA if the user wants it included.
- Stable form answers such as email, phone, location, work authorization, relocation, travel preference, and portfolio/LinkedIn.
- Any facts that must never be used in applications.

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
  "experience": [
    {
      "company": "",
      "location": "",
      "title": "",
      "start_date": "",
      "end_date": "",
      "bullets": [
        {
          "id": "company_role_01",
          "text": "Evidence-based resume bullet tied to this role.",
          "tags": ["Skill", "Tool", "Domain"]
        }
      ]
    }
  ],
  "education": [
    {
      "school": "",
      "degree": "",
      "location": "",
      "start_year": "",
      "end_year": "",
      "gpa": ""
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
