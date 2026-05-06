# NxJob API Schema

## API Rules

- Phase 1 uses REST only.
- Request and response shapes must stay compatible with future MCP tool schemas.
- Every mutating workflow response includes `trace_id`.
- AI workflows store `PromptLog`.
- User confirmation stays in the extension UI. APIs may draft, analyze, or record, but must not submit applications.
- Error responses use one common shape.

## Common Types

### ErrorResponse

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": {}
  },
  "trace_id": "string"
}
```

### SponsorshipStatus

```text
supports
does_not_support
likely_supports
likely_not_supports
needs_confirmation
unknown
```

### ApplicationStatus

```text
captured
reviewing
skipped
tailored
ready_to_apply
applied
replied
interviewing
offer
rejected
closed
```

## Endpoints

### GET /health

Purpose: verify the local service is running.

Response:

```json
{
  "status": "ok",
  "service": "nxjob-local-service",
  "version": "0.1.0"
}
```

### POST /api/v1/job-leads/capture

Purpose: capture the user-selected JD and page context.

Request:

```json
{
  "source_url": "string",
  "source_site": "linkedin",
  "page_title": "string",
  "selected_text": "string",
  "page_text_excerpt": "string",
  "platform_insights": {},
  "search_query": "string",
  "user_notes": "string"
}
```

Response:

```json
{
  "trace_id": "string",
  "job_lead": {
    "id": "string",
    "company_name": "string",
    "job_title": "string",
    "location": "string",
    "status": "captured",
    "jd_hash": "string"
  },
  "dedupe": {
    "is_duplicate": false,
    "existing_job_lead_id": null
  }
}
```

### GET /api/v1/job-leads/{job_lead_id}

Purpose: read one captured job lead.

Response:

```json
{
  "id": "string",
  "source_url": "string",
  "source_site": "company_ats",
  "status": "captured",
  "jd_text": "string"
}
```

### POST /api/v1/sponsorship/analyze

Future MCP tool name: `analyze_sponsorship`.

Purpose: analyze sponsorship support using JD rules first, then AI and public evidence only when needed.

Request:

```json
{
  "job_lead_id": "string",
  "jd_text": "string",
  "company_name": "string",
  "job_url": "string",
  "application_form_text": "string",
  "allow_public_lookup": true,
  "allow_ai": true
}
```

Response:

```json
{
  "trace_id": "string",
  "sponsorship": {
    "status": "needs_confirmation",
    "confidence": 0.62,
    "summary": "string",
    "risk_flags": ["string"],
    "questions_to_confirm": ["string"],
    "is_legal_conclusion": false
  },
  "evidence": [
    {
      "source": "jd_text",
      "evidence_text": "string",
      "evidence_url": "string",
      "confidence": 0.8
    }
  ],
  "ai_used": false
}
```

### POST /api/v1/resumes/tailor

Future MCP tool name: `tailor_resume`.

Purpose: generate a tailored DOCX resume from a JD, master resume bullets, and success references.

Request:

```json
{
  "job_lead_id": "string",
  "master_resume_id": "string",
  "master_resume_bullets": [
    {
      "id": "string",
      "text": "string",
      "tags": ["string"]
    }
  ],
  "constraints": {
    "format": "docx",
    "target_length": "one_page_preferred",
    "ats_friendly": true
  },
  "success_reference_limit": 3
}
```

Response:

```json
{
  "trace_id": "string",
  "resume_version": {
    "id": "string",
    "file_path": "string",
    "format": "docx",
    "selected_bullets": ["string"],
    "change_summary": "string"
  },
  "used_success_references": ["string"],
  "warnings": ["string"]
}
```

### POST /api/v1/forms/draft-answer

Future MCP tool name: `draft_form_answer_from_resume_bullets`.

Purpose: draft an answer for the current form field using profile facts and master resume bullets.

Request:

```json
{
  "job_lead_id": "string",
  "application_id": "string",
  "field_context": {
    "label": "string",
    "placeholder": "string",
    "surrounding_text": "string",
    "current_value": "string"
  },
  "jd_text": "string",
  "master_resume_bullets": [
    {
      "id": "string",
      "text": "string",
      "tags": ["string"]
    }
  ],
  "profile_vault_id": "string"
}
```

Response:

```json
{
  "trace_id": "string",
  "draft": {
    "id": "string",
    "answer": "string",
    "referenced_bullets": ["string"],
    "risk_flags": ["string"],
    "requires_user_review": true
  },
  "ai_used": true
}
```

### POST /api/v1/applications

Purpose: record a user-confirmed application event.

Request:

```json
{
  "job_lead_id": "string",
  "resume_version_id": "string",
  "application_url": "string",
  "application_method": "external_ats",
  "submitted_by_user": true,
  "user_notes": "string"
}
```

Response:

```json
{
  "trace_id": "string",
  "application": {
    "id": "string",
    "job_lead_id": "string",
    "resume_version_id": "string",
    "status": "applied"
  }
}
```

### GET /api/v1/applications/{application_id}

Purpose: read one application record.

Response:

```json
{
  "id": "string",
  "job_lead_id": "string",
  "resume_version_id": "string",
  "status": "applied"
}
```

### POST /api/v1/resume-versions

Purpose: create a stored resume version record. M5 will replace manual record creation with `POST /api/v1/resumes/tailor`.

Response:

```json
{
  "trace_id": "string",
  "resume_version": {
    "id": "string",
    "job_lead_id": "string",
    "format": "docx",
    "file_path": "string"
  }
}
```

### GET /api/v1/resume-versions/{resume_version_id}

Purpose: read one resume version record.

Response:

```json
{
  "id": "string",
  "job_lead_id": "string",
  "format": "docx",
  "file_path": "string"
}
```

### POST /api/v1/outcomes

Purpose: record a reply, screen, interview, rejection, offer, or other outcome.

Request:

```json
{
  "application_id": "string",
  "job_lead_id": "string",
  "outcome_type": "screen",
  "outcome_at": "string",
  "source": "manual",
  "evidence_text": "string",
  "user_notes": "string"
}
```

Response:

```json
{
  "trace_id": "string",
  "outcome": {
    "id": "string",
    "outcome_type": "screen"
  },
  "success_reference": {
    "created": true,
    "id": "string"
  }
}
```

## Validation Rules

- `selected_text` or `jd_text` is required when capturing or analyzing a job.
- `submitted_by_user` must be true to create an `applied` application event.
- Sponsorship AI inference must include `is_legal_conclusion: false`.
- `draft-answer` must return `requires_user_review: true`.
- `tailor-resume` MVP only returns `format: docx`.

