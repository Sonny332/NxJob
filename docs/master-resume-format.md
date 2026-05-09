# Master Resume Format

MVP uses a local JSON master resume file. This is the only runtime format NxJob reads today.

Users may start from an existing `.md`, `.txt`, `.doc`, or `.docx` resume, but that source should be converted into this JSON format before NxJob uses it. See `docs/master-resume-builder.md` for the planned AI-assisted conversion flow.

Set the local JSON path with `NXJOB_MASTER_RESUME_PATH`, or save it through the plugin setup UI when available.

Example:

```json
{
  "id": "master_default",
  "candidate_name": "Candidate Name",
  "contact_line": "City, ST | email@example.com | 555-000-0000 | linkedin.com/in/example",
  "bullets": [
    {
      "id": "backend_api_01",
      "text": "Built Python FastAPI services with SQLite-backed workflow automation.",
      "tags": ["Python", "FastAPI", "SQLite", "automation"]
    }
  ],
  "experience": [
    {
      "company": "Example Company",
      "location": "City, ST",
      "title": "Operations Analyst",
      "start_date": "2024",
      "end_date": "Present",
      "bullets": [
        {
          "id": "example_company_api_01",
          "text": "Automated Python API workflows for operational reporting.",
          "tags": ["Python", "API", "operations"]
        }
      ]
    }
  ],
  "education": [
    {
      "school": "Example University",
      "degree": "M.S. in Example Field",
      "location": "City, ST",
      "start_year": "2018",
      "end_year": "2020",
      "gpa": "3.62 / 4.0"
    }
  ],
  "fixed_answers": {
    "email": "email@example.com",
    "phone": "555-000-0000",
    "current location": "City, ST",
    "work authorization": "Requires employer sponsorship now or in the future."
  }
}
```

## Fields

- `id`: stable local id for this master resume.
- `candidate_name`: display name for generated DOCX.
- `contact_line`: optional contact line for generated DOCX.
- `bullets`: reusable cross-role evidence bullets for resume tailoring and form answers.
- `experience`: structured work history. Tailor Resume uses this to preserve company, title, location, and date ranges instead of flattening all evidence into disconnected bullets.
- `experience[].bullets`: evidence bullets tied to a specific role. Prefer this for resume-ready work history.
- `education`: structured education entries. Include years; Tailor Resume uses them for quality checks.
- `fixed_answers`: local-only answers for stable personal facts. These should be used without AI.

## Rules

- Keep the real file under `private/` or another ignored local path.
- Commit only synthetic examples or schema docs.
- Use short, evidence-based bullets with useful tags.
- Preserve all known work periods in `experience`; weaker roles can have fewer bullets, but should not disappear if that would create a time gap.
- Use consistent date strings such as `2024` / `Present` or `Jan 2024` / `Present`.
- Avoid storing secrets such as API keys, passwords, SSNs, or full immigration documents.
- Runtime workflows should load validated JSON only. Free-form resume sources belong to the future builder/import flow, not direct tailoring.
