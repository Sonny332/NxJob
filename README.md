# NxJob

NxJob is a lightweight job-application copilot. It is designed to reduce repetitive work around job description capture, sponsorship analysis, resume tailoring, form-answer drafting, and application tracking.

## Status

NxJob is a public MVP preview. The default distribution path is release artifacts, not source-code setup.

## User Install Path

For non-technical users, NxJob should be distributed as:

- a Windows local-service installer, and
- a packaged Chromium browser extension.

Use `docs/install-windows.md` for the installer path.

Current MVP installer note: download the latest `NxJob-<version>.zip` release package, unzip it, and use the root `.bat` files for install, start, status, stop, and uninstall. Do not use GitHub's auto-generated source-code zip as the normal user install path.

The Windows local-service package requires Python 3.11+ on the user's machine.

## MVP Scope

The MVP focuses on three browser actions plus a lightweight tracking loop:

- Analyze Sponsorship
- Tailor Resume
- Fill Form Answer
- Record Application / Outcome from the Side Panel

NxJob does not automatically submit applications, bypass verification, bulk scrape job sites, or perform no-confirmation mass applying.

Tailor Resume uses a private Master Resume, a configured resume output folder, and the local service to generate DOCX and Markdown resume artifacts. Generated resumes and private configuration stay local.

## Known MVP Limits

- Fill Form Answer drafts and fills detected fields, but the user must review every answer and submit manually.
- JD capture still works best when the user selects the job description text before capture.
- Tailor Resume output is usable for MVP testing, but layout and model-specific quality can still improve.
- Windows is the primary tested platform. Core business logic is kept platform-neutral for future macOS support.

## License and Privacy

NxJob source code is licensed under the Apache License 2.0.

User data is not part of the open-source repository. Do not commit real master resumes, generated resumes, AI provider API keys, local SQLite databases, PromptLogs, recruiter replies, or real application records. Keep those files in local private storage only.

## Developer Setup

Developer setup is secondary to packaged releases.

Expected stack:

- Extension: WXT, React, TypeScript
- Local service: Python, FastAPI
- Database: SQLite
- Resume output: DOCX first

Common developer checks:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-local-service.ps1
npm run shared:check
npm run extension:typecheck
npm run extension:build
```

Build MVP release artifacts:

```powershell
.\scripts\package\build-release.ps1 -Version <version>
```

Validate existing release artifacts:

```powershell
.\scripts\package\validate-release.ps1 -Version <version>
```
