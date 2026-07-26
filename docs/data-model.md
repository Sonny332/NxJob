# NxJob Data Model

## Principles

- Local-first data. SQLite is the MVP database.
- Store enough evidence to explain every AI or rule-based recommendation.
- Do not store secrets in plain application tables.
- Keep source snapshots: JD, resume version, form question, and outcome evidence must be traceable.
- Successful outcomes must feed future resume tailoring through `SuccessReference`.
- The saved-answer library is not stored in SQLite. It lives only in the Local Service private JSON file at `%LOCALAPPDATA%\NxJob\private\form-answer-library.v1.json`.

## Core Objects

### JobLead

Represents a captured job before or after application.

Fields:

- `id`: stable local id.
- `source_url`: original job or ATS URL.
- `source_site`: `linkedin`, `indeed`, `company_ats`, `other`.
- `company_name`.
- `job_title`.
- `location`.
- `captured_at`.
- `jd_text`.
- `jd_hash`: dedupe key.
- `platform_insights`: raw or summarized LinkedIn Premium, Indeed, or visible platform notes.
- `search_query`: search terms or source path used by the user.
- `status`: `captured`, `reviewing`, `skipped`, `tailored`, `ready_to_apply`, `applied`, `replied`, `interviewing`, `offer`, `rejected`, `closed`.
- `user_notes`.

### Application

Represents a real application attempt.

Fields:

- `id`.
- `job_lead_id`.
- `resume_version_id`.
- `applied_at`.
- `application_url`.
- `application_method`: `easy_apply`, `external_ats`, `email`, `other`.
- `status`: same status family as `JobLead`, but scoped to application progress.
- `submitted_by_user`: boolean.
- `follow_up_at`.
- `user_notes`.

### ResumeVersion

Represents a generated or imported resume version.

Fields:

- `id`.
- `job_lead_id`.
- `source_master_resume_id`.
- `created_at`.
- `format`: `docx`.
- `file_path`.
- `selected_bullets`: structured list of evidence bullets used.
- `change_summary`.
- `ai_output_json`.
- `prompt_log_id`.
- `version_label`.
- `user_approved`: boolean.

### SponsorshipEvidence

Represents sponsorship status and supporting evidence.

Fields:

- `id`.
- `job_lead_id`.
- `created_at`.
- `status`: `supports`, `does_not_support`, `likely_supports`, `likely_not_supports`, `needs_confirmation`, `unknown`.
- `confidence`: number from 0 to 1.
- `source`: `jd_text`, `application_form`, `company_site`, `government_data`, `recruiter_message`, `user_note`, `ai_inference`, `third_party`.
- `evidence_text`.
- `evidence_url`.
- `is_legal_conclusion`: always false.
- `prompt_log_id`.

### FormAnswerDraft

Represents an answer draft for one form question.

Fields:

- `id`.
- `job_lead_id`.
- `application_id`.
- `created_at`.
- `field_label`.
- `field_placeholder`.
- `surrounding_text`.
- `question_type`: `fixed_profile`, `open_question`, `work_authorization`, `other`.
- `draft_answer`.
- `referenced_bullets`.
- `risk_flags`.
- `user_edited_answer`.
- `filled_by_user_confirmation`: boolean.
- `prompt_log_id`.

Current scope note:

- `FormAnswerDraft` is the legacy AI-draft record shape. It is not the active storage for the saved-answer library.
- Confirmed saved answers are stored only in the Local Service private JSON file and are never copied into browser-offline storage, cloud sync, or `PromptLog`.
- Legacy workspace AI drafts must not be migrated into the service-backed saved-answer library.

### SavedAnswerLibrary File

Represents the service-owned saved-answer store outside SQLite.

Backing path:

- `%LOCALAPPDATA%\NxJob\private\form-answer-library.v1.json`

Ownership and lifecycle:

- The Local Service is the only process that owns and writes this file.
- The browser extension may migrate once from its old `nxjob.form-answer-library.v1` key into this file, then reads and writes the library only through loopback REST.
- Removing an old extension instance also removes that extension's Chrome storage, so deleted-extension browser data cannot be recovered afterward.
- A replacement extension can still read the same saved answers immediately once the Local Service is running, because the active library is keyed only by the service file path, not by an extension installation id.

Stored fields per answer:

- `id`
- `question`
- `normalizedQuestion`
- `fieldType`
- `answers`
- `sensitive`
- `createdAt`
- `updatedAt`
- `lastUsedAt`

### SuccessReference

Represents a positive market signal used for future tailoring.

Fields:

- `id`.
- `application_id`.
- `job_lead_id`.
- `resume_version_id`.
- `outcome_type`: `positive_reply`, `screen`, `interview`, `offer`.
- `outcome_at`.
- `source`: `email`, `manual`, `recruiter_message`, `calendar`.
- `search_query`.
- `effective_keywords`.
- `effective_bullets`.
- `user_notes`.

### ProfileVault

Represents reusable personal information and stable facts.

Fields:

- `id`.
- `profile_name`.
- `location`.
- `work_authorization_summary`.
- `sponsorship_need_summary`.
- `contact_fields`.
- `fixed_answers`.
- `master_resume_bullets`.
- `updated_at`.

### PromptLog

Represents one AI workflow call.

Fields:

- `id`.
- `trace_id`.
- `workflow_name`: `analyze_sponsorship`, `tailor_resume`, `draft_form_answer_from_resume_bullets`.
- `created_at`.
- `input_summary`.
- `model`.
- `provider`.
- `token_usage`.
- `output_summary`.
- `raw_output_path`.
- `error`.

### OutcomeSignal

Represents a tracked result that may or may not become a success reference.

Fields:

- `id`.
- `application_id`.
- `job_lead_id`.
- `created_at`.
- `outcome_type`: `positive_reply`, `screen`, `interview`, `offer`, `rejection`, `no_response`, `closed`.
- `source`.
- `evidence_text`.
- `evidence_url`.
- `user_notes`.

## Relationships

- `JobLead` has many `SponsorshipEvidence`.
- `JobLead` has many `ResumeVersion`.
- `JobLead` has many `Application`.
- `Application` references one submitted `ResumeVersion`.
- `Application` has many `OutcomeSignal`.
- `SuccessReference` references one positive `OutcomeSignal` through `Application`, `JobLead`, and `ResumeVersion`.
- `PromptLog` can be linked by `ResumeVersion`, `SponsorshipEvidence`, or `FormAnswerDraft`.

## MVP Constraints

- Do not delete source snapshots by default.
- Do not treat AI sponsorship inference as a legal conclusion.
- Do not store API keys inside these data tables.
- Do not require email sync for MVP; manual outcome entry is enough for M7.

