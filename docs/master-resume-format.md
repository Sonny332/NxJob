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
- `bullets`: reusable evidence bullets for resume tailoring and form answers.
- `fixed_answers`: local-only answers for stable personal facts. These should be used without AI.

## Rules

- Keep the real file under `private/` or another ignored local path.
- Commit only synthetic examples or schema docs.
- Use short, evidence-based bullets with useful tags.
- Avoid storing secrets such as API keys, passwords, SSNs, or full immigration documents.
- Runtime workflows should load validated JSON only. Free-form resume sources belong to the future builder/import flow, not direct tailoring.
