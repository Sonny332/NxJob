# Release Test Record

Use this file as the template for each release. Copy it into the release notes or attach it to the GitHub release.

## Version

- Version:
- Commit:
- Date:
- Tester:

## Artifacts

- Local service package:
- Browser extension package:
- Release manifest:

## Checks

- `python -m pytest apps/local-service/tests -q`:
- `npm run shared:check`:
- `npm run extension:typecheck`:
- `npm run extension:build`:
- `scripts/package/build-release.ps1`:

## Manual Smoke Test

- Local service install script completed:
- `GET /health` returns ok:
- Browser extension loads:
- Analyze Sponsorship button works:
- Tailor Resume button creates a DOCX:
- Fill Form Answer drafts and fills only after confirmation:
- Outcome entry creates SuccessReference:

## Data Boundary

- Real master resume is local only:
- `private/` not included in Git diff:
- Generated resumes not included in Git diff:
- SQLite database not included in Git diff:

## Version Differences

- Added:
- Changed:
- Fixed:
- Known limits:
