# Service-Backed Answer Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve confirmed answers across extension replacement by storing them in the Local Service private JSON file.

**Architecture:** The Local Service owns `%LOCALAPPDATA%\NxJob\private\form-answer-library.v1.json` and exposes localhost CRUD/import REST. The extension uses this service as the only active answer library and treats Chrome storage only as a one-time source for current confirmed-answer migration.

**Tech Stack:** FastAPI, Pydantic, Python standard library JSON/path APIs, React, TypeScript, WXT, Node assert.

## Global Constraints

- No dependency, cloud sync, Chrome sync storage, AI, automatic fill, automatic selection, or submission.
- Sensitive answers stay local and never enter logs, Git, AI, or a non-local request.
- Service offline allows scan only. Candidate display, Copy, and Save show a start-service recovery message.
- Import `nxjob.form-answer-library.v1` only. Never convert `nxjob.workspace.v1` AI drafts.
- Gate: GPT-5.6 Sol / High Planner, GPT-5.4 / Medium Implementer, independent GPT-5.6 Sol / High Reviewer.

## Service Contract

- `GET /api/v1/form-answer-library` returns `{ trace_id, version: 1, answers }`.
- `POST /api/v1/form-answer-library/import` merges `{ answers }` by normalized question, field type, and answer array.
- POST, PUT, touch POST, single DELETE, and collection DELETE routes provide save, edit, touch, delete, and clear.
- The document keeps the existing `SavedAnswer` fields: id, question, normalizedQuestion, fieldType, answers, sensitive, and timestamps.
- Writes use a sibling temporary file plus `Path.replace()`.

### Task 1: Service storage and API

**Files:** Create `apps/local-service/src/nxjob/api/form_answer_library.py` and `apps/local-service/tests/api/test_form_answer_library.py`. Modify `apps/local-service/src/nxjob/settings/private_config.py`, `apps/local-service/src/nxjob/schemas/core.py`, and `apps/local-service/src/nxjob/main.py`.

- [ ] Write failing tests for empty read, CRUD, idempotent import, malformed JSON preserving the previous valid file, and clear preserving unrelated private config.
- [ ] Run `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-local-service.ps1 apps/local-service/tests/api/test_form_answer_library.py -q`; expect missing-route failure.
- [ ] Implement path, strict Pydantic validation, atomic write, deduplicating import, and router registration.
- [ ] Run the same wrapper; expect focused service tests to pass.
- [ ] Commit with `feat(service): persist confirmed form answers`.

### Task 2: Extension service client and migration

**Files:** Modify `apps/extension/src/lib/api-client.ts`, `apps/extension/src/lib/form-answer-library.ts`, and `apps/extension/tests/form-answer-library.test.mjs`.

- [ ] Write failing tests proving current browser confirmed answers load once, the migration marker blocks a second import, and `nxjob.workspace.v1` is never read.
- [ ] Run `npm --workspace @nxjob/extension run test:answers`; expect migration-helper failure.
- [ ] Add typed calls for the service contract. Keep matching pure. Read browser data only through explicit migration helpers; write the marker only after successful import; do not clear browser data.
- [ ] Convert fetch failure into `Local Service is unavailable. Start it to use saved answers.` without answer payloads.
- [ ] Re-run `test:answers`; expect matching and migration tests to pass.
- [ ] Commit with `feat(extension): migrate answers to local service`.

### Task 3: Side panel ownership and offline scan-only state

**Files:** Modify `apps/extension/entrypoints/sidepanel/App.tsx`, `apps/extension/entrypoints/sidepanel/style.css`, and `apps/extension/tests/sidepanel-form-answer.test.mjs`.

- [ ] Write a failing assertion that Find Form Answers stays enabled offline while candidate display, Copy, and Save require service availability and display the recovery text.
- [ ] Run `npm --workspace @nxjob/extension run test:sidepanel`; expect failure.
- [ ] On service availability, load service answers, run one-time browser import, reload service answers, and use service CRUD. Offline retains detected fields but has no candidates or answer actions.
- [ ] Run `test:sidepanel`, `test:answers`, and `test:capture`; expect all pass.
- [ ] Commit with `feat(extension): require service for answer library`.

### Task 4: Documentation and verification

**Files:** Modify `docs/api-schema.md`, `docs/data-model.md`, `docs/privacy-boundary.md`, and `README.md`.

- [ ] Document path, service ownership, migration limit, no-AI/no-cloud rule, and offline scan-only state. Do not claim recovery after uninstallation.
- [ ] Run `npm --workspace @nxjob/extension run test:answers`, `npm --workspace @nxjob/extension run test:sidepanel`, `npm --workspace @nxjob/extension run test:capture`, `npm run extension:typecheck`, `npm run extension:build`, and `git diff --check`.
- [ ] Run `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-local-service.ps1 apps/local-service/tests/api/test_form_answer_library.py -q`; if the documented ACL failure occurs, rerun only this wrapper sandbox-external as the ordinary user.
- [ ] Smoke with synthetic answers only: save text and sensitive test answers, replace/reload extension, verify candidates return, stop service and verify scan-only state, then restart service and verify candidates return.
- [ ] Commit with `docs: document service-backed answer library`.

## Reviewer Checklist

- Reject path traversal, non-atomic writes, answer-content logging, non-local requests, browser offline fallback, or migration from workspace drafts.
- Independently rerun the service wrapper and `test:answers`.
- Verify offline leaves scan available but blocks candidates, copy, and save.
- Verify Workday searchable-dropdown behavior is unchanged.

## Acceptance Criteria

- Service private JSON is the only active answer library.
- A replacement extension reads the same service library without a prior extension ID.
- Browser confirmed answers migrate once; legacy AI drafts never migrate.
- No answer content reaches AI, logs, cloud, Git, or a non-local process.
