# NxJob Release Notes Template

## Version

`vX.Y.Z`

Versioning follows `docs/versioning.md`.

## User-Facing Changes

- 

## Install

Download:

- `NxJob-X.Y.Z.zip`
- `nxjob-local-service-X.Y.Z.zip`
- `nxjob-extension-X.Y.Z.zip`

Follow `docs/install-windows.md`.

For non-technical users, use `NxJob-X.Y.Z.zip`. Do not use GitHub's automatic `Source code (zip)` archive as an installer.

## Known Limits

- Windows-first MVP.
- Local-service installer script requires Python 3.11+ and may need network access for dependencies.
- REST-only Phase 1.
- No MCP server yet.
- No automatic application submission.
- No LinkedIn/Indeed bulk scraping.
- DOCX validation is basic until document validation adapters are expanded.

## Verification

Attach or paste the completed release test record.

## Release Assets

Upload files from local folder:

```text
releases/X.Y.Z/
```

Required assets:

- `NxJob-X.Y.Z.zip`
- `nxjob-local-service-X.Y.Z.zip`
- `nxjob-extension-X.Y.Z.zip`
- `release-manifest.json`
- `release-test-record-X.Y.Z.md`

The manifest commit must match the release tag commit.
