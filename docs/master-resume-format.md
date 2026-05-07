# Master Resume Format

MVP uses a local JSON master resume file. Set its path with `NXJOB_MASTER_RESUME_PATH`.

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
