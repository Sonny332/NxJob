# NxJob

NxJob is a lightweight job-application copilot. It is designed to reduce repetitive work around job description capture, sponsorship analysis, resume tailoring, form-answer drafting, and application tracking.

## Status

NxJob is in MVP development. A public installer is not available yet.

## User Install Path

For non-technical users, NxJob should be distributed as:

- a Windows local-service installer, and
- a packaged Chromium browser extension.

Source setup and development scripts are not the default user path.

## MVP Scope

The MVP focuses on three browser actions:

- Analyze Sponsorship
- Tailor Resume
- Fill Form Answer

NxJob does not automatically submit applications, bypass verification, bulk scrape job sites, or perform no-confirmation mass applying.

## Developer Setup

Developer instructions will be finalized during M1 and M2.

Expected stack:

- Extension: WXT, React, TypeScript
- Local service: Python, FastAPI
- Database: SQLite
- Resume output: DOCX first

