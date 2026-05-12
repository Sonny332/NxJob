# NxJob MVP Scope

## MVP Goal

NxJob MVP proves the smallest useful loop:

```text
Capture JD -> Analyze Sponsorship -> Tailor Resume -> Draft Form Answer -> Record Application -> Record Positive Outcome -> Reuse Success Reference
```

The MVP is a lightweight browser-extension-driven assistant, not a job discovery platform.

## In Scope

User layer:

- Browser extension with three buttons:
  - `Analyze Sponsorship`
  - `Tailor Resume`
  - `Fill Form Answer`
- User review and confirmation before applying or filling answers.
- Visible local service connection status.

Local runtime layer:

- FastAPI local service.
- SQLite local database.
- REST endpoints listed in `api-schema.md`.
- JobLead capture and dedupe by URL/hash.
- Sponsorship evidence record.
- DOCX resume generation.
- Form answer draft storage.
- Application and outcome tracking.
- SuccessReference creation for positive replies, screens, interviews, and offers.

AI layer:

- Sponsorship fallback only when JD and local rules are insufficient.
- Resume content selection and rewrite.
- Complex form answer drafting.
- Master Resume Builder is documented as a future helper flow; MVP runtime uses validated JSON only.

## Out of Scope for MVP

- LinkedIn or Indeed bulk scraping.
- Automatic application submission.
- CAPTCHA bypass or automated site navigation.
- MCP server implementation.
- Extension as MCP client.
- Email sync.
- Full interview simulator.
- PDF generation as a required output.
- Strict one-page validation.
- Cross-platform installer.
- Cloud sync.
- Direct runtime tailoring from `.md`, `.txt`, `.doc`, or `.docx` master resume sources.

## Milestone Granularity

NxJob is a personal MVP. Future milestones should represent user-visible progress, not every internal implementation step.

Recommended milestone families:

- Core Capture & Local Service
- Sponsorship & Decision Aid
- Resume Tailor Usable Loop
- Form Answer & Application Tracking
- Release & Daily Use Hardening
- Post-MVP Learning / Success Feedback

Do not create separate milestones for a single UI copy change, test fix, schema field, provider preset, small bug fix, or documentation correction unless the change carries unusual risk.

The detailed M0-M8 list below records the historical build plan and can still be used as implementation context. It should not force future work into the same level of fragmentation.

## Historical MVP Milestone Exit Criteria

M0 exits when:

- `tech-stack.md`, `project-structure.md`, `data-model.md`, `api-schema.md`, and `mvp-scope.md` exist.
- They agree with `product-blueprint.md`.
- They define enough detail to create the repo skeleton without new product decisions.

M1 exits when:

- WXT extension scaffold exists.
- FastAPI local service scaffold exists.
- `GET /health` works.
- Shared schema package exists.

M2 exits when:

- SQLite initializes repeatably.
- CRUD exists for `JobLead`, `Application`, and `ResumeVersion`.
- Workflow calls produce a `trace_id`.

M3 exits when:

- Extension can read URL, title, selected text, and basic page text.
- Three buttons are visible.
- Missing local service state is handled.

M4 exits when:

- Sponsorship rules identify explicit support and explicit non-support without AI.
- Ambiguous cases can call AI fallback.
- Evidence and status are saved.

M5 exits when:

- A sample JD and master resume bullets generate a DOCX.
- The generated `ResumeVersion` is saved.
- Success references can be included in the tailoring input.

M6 exits when:

- A sample form question produces a draft answer.
- User confirmation is required before filling the field.
- No submit action is performed.

M7 exits when:

- A positive outcome creates a `SuccessReference`.
- A future tailor request can retrieve similar success references.

M8 exits when:

- Windows local service installer exists.
- Extension package exists.
- Release checklist and packaging test result are recorded.

## Platform Scope

MVP is Windows-first for packaging and user installation.

Core business code must stay platform-neutral. OS-specific differences may only appear in packaging, path adapter, service startup adapter, and document validation adapter modules.
