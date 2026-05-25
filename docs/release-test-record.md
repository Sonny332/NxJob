# Release Test Record

Use this file as the template for each release. Copy it into the release notes or attach it to the GitHub release.

## Version

- Version:
- Commit:
- Date:
- Tester:

## Artifacts

- One-click Windows package:
- Local service package:
- Browser extension package:
- Release manifest:

## Checks

- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/test-local-service.ps1`:
- `npm run shared:check`:
- `npm run extension:typecheck`:
- `npm run extension:build`:
- `scripts/package/build-release.ps1`:
- `scripts/package/validate-release.ps1`:

## Manual Smoke Test

- Local service install script completed:
- `Install NxJob Local Service.bat` completes:
- `Start NxJob Local Service.bat` starts the service:
- `Check NxJob Local Service.bat` returns ok:
- `Status NxJob Local Service.bat` reports healthy:
- Browser extension loads:
- Analyze Sponsorship button works:
- Tailor Resume button creates a DOCX:
- Fill Form Answer drafts and fills only after confirmation:
- Outcome entry creates SuccessReference:
- `Stop NxJob Local Service.bat` stops the service:
- `Uninstall NxJob Local Service.bat` removes service files:

## Data Boundary

- Real master resume is local only:
- `private/` not included in Git diff:
- Generated resumes not included in Git diff:
- SQLite database not included in Git diff:
- Release zips do not contain private data:

## Version Differences

- Added:
- Changed:
- Fixed:
- Known limits:
