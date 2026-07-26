# Privacy Boundary

NxJob is local-first. Private job search data must stay on the user's machine by default.

For the service-backed saved-answer library, the private canonical file is `%LOCALAPPDATA%\NxJob\private\form-answer-library.v1.json`. The Local Service is the only owner of that file.

## Never Commit

Do not commit these files or directories:

- `private/`
- `%LOCALAPPDATA%\NxJob\private\form-answer-library.v1.json`
- Real master resume files.
- Generated tailored resumes.
- Local SQLite databases.
- Prompt logs containing private resume or job application content.
- Real application records, recruiter replies, or interview notes.
- AI provider API keys and private provider config files.

## Repository-Safe Content

The repository may contain:

- Schema definitions.
- Parser and renderer code.
- Synthetic fixtures.
- Documentation.
- Tests using fake resume and job data.

The repository must not contain:

- exported or copied saved-answer libraries from real use
- browser storage dumps with confirmed answers
- workspace AI drafts copied into the saved-answer library

## MVP Rule

During MVP development, a real master resume may be used only as a local private file. The local service can read it through `NXJOB_MASTER_RESUME_PATH`, but the file must not be staged, committed, or uploaded to GitHub.

Current local MVP setup may place the user's real master resume at `private/master-resume/`. This directory is intentionally ignored by Git.

## Future Direction

NxJob should later provide a helper skill or UI flow that converts a normal resume into the structured master resume format. That generated file still belongs to local private storage unless the user explicitly exports it.

The runtime should continue to use validated JSON as the canonical master resume format. Uploaded `.md`, `.txt`, `.doc`, or `.docx` resumes are import sources only; they should be converted, reviewed, and saved under local private config before use.

AI provider presets, base URLs, model names, and API keys are stored by the local service in private config. API keys must not appear in GitHub, release packages, PromptLog, or plugin-visible error details.

## Saved Answer Boundary

- Confirmed saved answers are local only. They do not go to AI, cloud sync, Git, analytics, or any non-local process.
- The extension may migrate once from the old browser key `nxjob.form-answer-library.v1` into the Local Service file. It must never migrate workspace state, AI drafts, or `nxjob.workspace.v1`.
- There is no supported browser-offline answer-library copy after migration. If the Local Service is down, the extension may still scan the page structure locally, but it must not display, save, edit, delete, clear, or copy answers.
- If a user deletes an older extension installation, that installation's Chrome storage is gone and NxJob cannot recover it later. A newly installed extension can still read the Local Service answer library directly once the service is running.
- As of July 26, 2026, P1b remains intentionally deferred: NxJob still relies on the local machine trust boundary for which local extensions or processes can reach the loopback service. CORS only shapes browser fetch behavior; it does not authenticate callers or block arbitrary local processes.

## Current Recognition Limits

- Workday searchable dropdowns, multi-level dropdowns, and other search-in-dropdown controls remain manual-selection cases in the current milestone.
- NxJob should not promise automatic recovery or automatic answer capture for those controls until the product behavior actually changes.
