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
  "version": "0.4.3"
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

M4 implementation note: Phase 1 does not perform public web lookup yet. `allow_public_lookup` is accepted for MCP-compatible shape, but the local service ignores it until a later milestone. If local rules cannot decide and `allow_ai` is true, M4 uses a deterministic AI-fallback stub so the workflow, UI, trace, and evidence contracts are testable before a real provider is wired.

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

Rules:

- `job_lead_id` is required.
- If `jd_text` is empty, the local service reads `JobLead.jd_text`.
- Explicit sponsorship / no-sponsorship wording is handled locally and must return `ai_used: false`.
- Ambiguous wording may return `ai_used: true` when `allow_ai` is true.
- Every response must save workflow trace and sponsorship evidence.
- `is_legal_conclusion` must always be `false`.

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

Purpose: generate a tailored DOCX resume and matching Markdown file from a JD, master resume bullets, and success references.

M11 implementation note: Phase 1 uses a configured OpenAI-compatible provider when one is available, and falls back to deterministic local tailoring when no AI provider is configured. The workflow returns structured content, selected bullet ids, layout budget, quality checks, DOCX path, and Markdown path. It does not log full Master Resume, full JD, API key, or full prompt text.

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
  "success_reference_limit": 3,
  "output_directory_override": "",
  "force_refresh": false
}
```

Rules:

- `master_resume_bullets` is required unless a private Master Resume JSON is configured.
- If `master_resume_bullets` is omitted, the local service reads the private JSON file configured by `NXJOB_MASTER_RESUME_PATH`.
- MVP only supports `constraints.format: "docx"`.
- The generated DOCX and Markdown are written by the local service under the configured resume output folder.
- The default filename policy is `YYYY-MM-DD_<company>_<job-title>_resume`, with safe path characters and `_v2` suffixes for collisions.
- Each call creates a new `ResumeVersion`; repeated calls for the same JD preserve versions.
- `PromptLog` stores input summary, output summary, provider/model label, token-like usage, and trace id.
- When an AI provider is configured, provider failures return plugin-readable errors such as authentication failure, rate limit, network failure, timeout, provider unavailable, or invalid response. Error logs store only sanitized categories.
- When a private Master Resume has structured `experience` entries, generated content uses role-based `experience_sections` so company, title, location, and dates remain visible.
- AI provider config supports presets for common OpenAI-compatible services: OpenAI, DeepSeek, Gemini, OpenRouter, and custom endpoints. Known provider base URLs are normalized before calling `/chat/completions`, so users can provide either the service root or full API base path.
- Success references are retrieved by keyword overlap and returned as ids in `used_success_references`.
- Strict PDF/page-count validation is not part of M11; M11 uses budget checks plus basic DOCX existence validation and returns warnings.

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
  "warnings": ["string"],
  "ai_used": true,
  "ai_provider_name": "openai_compatible",
  "docx_path": "string",
  "markdown_path": "string",
  "filename_base": "string",
  "layout_budget": {
    "name_lines": 1,
    "heading_lines": 4,
    "body_lines": 32,
    "max_heading_lines": 5,
    "max_body_lines": 55
  },
  "quality_checks": {
    "one_page_budget_ok": true,
    "education_years_present": true,
    "summary_avoids_fixed_year_count": true,
    "experience_timeline_preserved": true
  }
}
```

### GET /api/v1/config/status

Purpose: report local private setup state used by the plugin setup panel.

Response includes:

```json
{
  "master_resume_configured": true,
  "ai_provider_configured": true,
  "resume_output_dir_configured": true,
  "resume_output_dir": "D:\\Resume\\NxJob Generated",
  "warnings": []
}
```

### POST /api/v1/config/resume-output-directory

Purpose: save the private local folder used for generated resumes.

Request:

```json
{
  "path": "D:\\Resume\\NxJob Generated"
}
```

Rules:

- The local service validates that the folder can be created and written.
- The configured path is stored in private local config and must not be committed, logged, or packaged.

### POST /api/v1/forms/draft-answer

Future MCP tool name: `draft_form_answer_from_resume_bullets`.

Purpose: draft an answer for the current form field using profile facts and master resume bullets.

M6 implementation note: fixed personal facts are read from the private master resume `fixed_answers` map and do not consume AI. Open-ended questions use the current JD, field context, and the smallest matching set of master resume bullets. The plugin must show the draft first; the user must explicitly confirm before NxJob fills the focused field. NxJob never clicks submit.

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

Rules:

- `job_lead_id` and `field_context` are required.
- `requires_user_review` is always `true`.
- Fixed answers can return `ai_used: false`.
- Open-ended answers return referenced bullet ids and risk flags.
- If `master_resume_bullets` is omitted, the local service reads `NXJOB_MASTER_RESUME_PATH`.
- Filling a field is a plugin UI confirmation action, not a backend submit action.

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

M7 implementation note: positive outcomes (`positive_reply`, `screen`, `interview`, `offer`) automatically create a `SuccessReference` when a matching `ResumeVersion` exists. Negative or closed outcomes update tracking status but do not become success references.

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

Rules:

- `job_lead_id` and `outcome_type` are required.
- If `application_id` is provided, it must belong to the same `JobLead`.
- Positive outcomes update `Application` and `JobLead` status and create a `SuccessReference`.
- `rejection`, `no_response`, and `closed` update status but do not create a `SuccessReference`.
- `SuccessReference.effective_bullets` is copied from the submitted `ResumeVersion.selected_bullets`.
- `SuccessReference.effective_keywords` is derived from the original JD text.

### GET /api/v1/success-references

Purpose: list positive market signals for tracker views and future tailoring.

Response:

```json
{
  "trace_id": "string",
  "success_references": [
    {
      "id": "string",
      "application_id": "string",
      "job_lead_id": "string",
      "resume_version_id": "string",
      "outcome_type": "screen",
      "outcome_at": "string",
      "search_query": "string",
      "effective_keywords": ["string"],
      "effective_bullets": ["string"]
    }
  ]
}
```

### GET /api/v1/success-references/{success_reference_id}

Purpose: read a success reference with its linked `JobLead`, `ResumeVersion`, and optional `Application`.

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

