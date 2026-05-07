# NxJob

NxJob is a lightweight job-application copilot. It is designed to reduce repetitive work around job description capture, sponsorship analysis, resume tailoring, form-answer drafting, and application tracking.

## Status

NxJob is in MVP development. The default distribution path is release artifacts, not source-code setup.

## User Install Path

For non-technical users, NxJob should be distributed as:

- a Windows local-service installer, and
- a packaged Chromium browser extension.

Use `docs/install-windows.md` for the installer path.

Current MVP installer note: the Windows local-service package uses a PowerShell installer script and requires Python 3.11+ on the user's machine.

## MVP Scope

The MVP focuses on three browser actions:

- Analyze Sponsorship
- Tailor Resume
- Fill Form Answer

NxJob does not automatically submit applications, bypass verification, bulk scrape job sites, or perform no-confirmation mass applying.

## Developer Setup

Developer setup is secondary to packaged releases.

Expected stack:

- Extension: WXT, React, TypeScript
- Local service: Python, FastAPI
- Database: SQLite
- Resume output: DOCX first

Common developer checks:

```powershell
python -m pytest apps\local-service\tests -q
npm run shared:check
npm run extension:typecheck
npm run extension:build
```

Build MVP release artifacts:

```powershell
.\scripts\package\build-release.ps1 -Version 0.1.0
```

