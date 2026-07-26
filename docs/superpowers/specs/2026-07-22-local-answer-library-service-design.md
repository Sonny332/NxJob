# Local Answer Library Service Design

## Goal

Store user-confirmed form answers in the Local Service private directory so they survive browser extension replacement and version updates.

## Scope

- The Local Service is the only persistent source of truth for confirmed form answers.
- The service stores a versioned JSON document at `%LOCALAPPDATA%\NxJob\private\form-answer-library.v1.json`.
- The extension reads and writes the library only through localhost REST endpoints.
- On first successful service connection, the extension migrates only the current `nxjob.form-answer-library.v1` browser records into an empty or compatible service library.
- Existing `nxjob.workspace.v1` records, including legacy AI drafts, are never migrated as confirmed answers.
- The extension retains the browser copy after migration and does not use it as a fallback source. It is not deleted automatically.

## Offline Behavior

- Form scanning remains available without the Local Service.
- Answer candidates are not shown while the Local Service is unavailable.
- Copy and `Save this answer` are unavailable while the Local Service is unavailable and explain that the service must be started.
- The extension does not create a second persistent browser-side answer cache while offline.

## Privacy And Safety

- Answers, including sensitive answers, remain on the local machine.
- Answer content is never sent to AI providers, remote APIs, logs, PromptLog, or Git.
- The service currently exposes the existing loopback REST boundary on the local machine. As of July 26, 2026, P1b caller authentication/origin restriction is intentionally deferred, so this boundary should be described as a local trust boundary rather than as authenticated extension-only access.
- JSON writes are atomic so an interrupted write does not corrupt the last valid library.

## Compatibility

- A newly installed extension automatically reads the service library, so its Chrome extension ID is irrelevant.
- The browser-to-service migration is idempotent: identical normalized question, field type, and answer arrays are deduplicated using the existing answer-library rule.
- The earlier deleted extension's storage cannot be recovered and is outside this migration.

## Exclusions

- No cloud synchronization, Chrome sync storage, AI use, automatic filling, automatic selection, or submission.
- No conversion of legacy AI drafts into confirmed answers.
- Workday searchable/custom dropdown value capture is a separate follow-up.

## Validation

- Local Service unit/API tests cover empty-library initialization, atomic read/write, validation, idempotent migration, and malformed JSON handling.
- Extension tests cover service-backed listing/matching, one-time migration, and offline scan-only behavior.
- Integration tests verify no answer content reaches AI or non-local endpoints.
- Manual smoke verifies extension replacement can read the same service library and that the offline UI blocks copy/save while preserving scan.
