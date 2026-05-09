# NxJob Tech Stack

## Decision

NxJob MVP uses a browser extension plus a local service.

- Extension: WXT, React, TypeScript.
- Local service: Python, FastAPI.
- Database: SQLite.
- Shared schema: JSON Schema as the source of truth, with generated TypeScript types and Python validation models.
- Resume output: DOCX first. PDF and strict page validation are post-MVP or later M5 enhancements.
- AI provider: OpenAI-compatible adapter with presets for OpenAI, DeepSeek, Gemini, OpenRouter, and custom endpoints. The provider must be replaceable behind one local service interface.
- Phase 1 integration: REST only. MCP server is not implemented in Phase 1, but REST request and response schemas must be compatible with future MCP tools.

## Rationale

- WXT keeps extension development close to the browser workflow and supports React UI surfaces for popup, side panel, and content scripts.
- FastAPI is the best fit for local workflows that need file generation, AI orchestration, SQLite, and Windows packaging.
- SQLite is enough for a personal local-first application and keeps installation simple.
- JSON Schema prevents extension and service models from drifting while keeping future MCP tool schemas close to the same contract.
- DOCX is the first real deliverable users need for applications. PDF and strict one-page validation should not block MVP.

## Runtime Boundaries

User layer:

- Browser extension buttons and UI.
- User review and confirmation.
- No automatic application submission.

Local runtime layer:

- REST API.
- Workflow orchestration.
- Cache and database.
- DOCX rendering.
- Form answer drafting runtime.
- Prompt and workflow logs.
- Future MCP server wrapper.

AI layer:

- Sponsorship ambiguity analysis when JD and local rules are insufficient.
- Resume evidence selection and rewrite.
- Complex form-answer drafting.

## Phase Rules

Phase 1:

- Implement three extension buttons: `Analyze Sponsorship`, `Tailor Resume`, `Fill Form Answer`.
- Implement REST endpoints for the three workflows.
- Store data locally.
- Keep schemas MCP-compatible.
- Do not implement MCP server.

Phase 2:

- Expose the same workflows as MCP tools: `analyze_sponsorship`, `tailor_resume`, `draft_form_answer_from_resume_bullets`.
- Reuse business logic. Do not fork the workflows for MCP.

Phase 3:

- Decide whether the extension continues using REST or becomes an MCP client.
- Allow external AI clients to call the NxJob MCP server.

## Tooling Defaults

Extension:

- Package manager: npm unless a later repo decision switches to pnpm.
- UI: React components inside WXT popup or side panel.
- Browser target: Chromium-based browsers first.

Local service:

- Python 3.11+.
- FastAPI and Uvicorn for the API server.
- Pydantic v2 for request and response validation.
- SQLAlchemy or SQLModel for SQLite persistence. Choose one during M1; prefer SQLModel if it reduces duplication.
- python-docx for MVP DOCX generation.

Testing:

- Extension: TypeScript type checks and browser smoke tests.
- Local service: pytest.
- API smoke: FastAPI TestClient.
- End-to-end browser verification can start in M3.

Packaging:

- Windows-first.
- Local service installer is required by M8.
- Extension package is distributed separately from the local service.

## Cross-Platform Constraint

MVP is Windows-first, but core business code must remain platform-neutral.

All OS-specific behavior must stay behind adapters:

- Packaging adapter: installer, app bundle, signing, and release artifact differences.
- Path adapter: app data, cache, logs, generated resumes, and user document paths.
- Service startup adapter: Windows service/startup shortcut, macOS launch agent or app startup, and future Linux options.
- Document validation adapter: Word COM, LibreOffice headless, PDF rendering, or other platform-specific validation backends.

Business workflows must not hard-code Windows paths, Windows shell commands, Word COM, registry access, or installer assumptions.
