# Release Hardening

M9 improves the MVP packaging flow without changing NxJob's product behavior.

Version numbers follow `docs/versioning.md`.

## Scope

- Keep Phase 1 REST-only.
- Keep private data out of release artifacts.
- Keep Windows-specific behavior inside packaging and service startup scripts.
- Improve the local-service package from a basic zip into an operational package with install, start, status, stop, health check, and uninstall scripts.
- Provide root-level `.bat` launchers so non-technical users can double-click common service actions without opening a command line.
- Validate generated artifacts before a release is considered usable.

## Release Artifact Contract

Each release folder should contain:

- `NxJob-<version>.zip`
- `nxjob-local-service-<version>.zip`
- `nxjob-extension-<version>.zip`
- `release-manifest.json`
- `release-test-record-<version>.md`

Run:

```powershell
.\scripts\package\build-release.ps1 -Version <version>
```

The build script runs automated checks, builds both packages, writes the release manifest, writes a release test record, and validates the artifacts.

`NxJob-<version>.zip` is the default user-facing package. Its zip root must contain the one-click `.bat` launchers. Users should not install from GitHub's automatic source archive because that archive preserves repository paths such as `scripts/package/local-service-root-scripts`.

The release folder is the source of truth for GitHub Release uploads:

```text
releases/<version>/
```

Before recommending publication, confirm `release-manifest.json` points to the same commit intended for tag `v<version>`. The explicit `build-release.ps1 -Version <version>` argument is the formal version input.

If the release build requires a packaging-script fix, commit the fix first, rebuild the release folder, then tag the new commit.

## Incremental Privacy Check

NxJob is already public. Every release must inspect the current tracked tree, release diff, generated artifacts, current Actions/workflow output, and user-visible logs/errors for private resume data, API keys, local databases, PromptLogs, generated resumes, recruiter replies, real application records, sensitive paths, and user-specific configuration.

Confirm the release package excludes private config, local app data, caches, source-control metadata, and other unapproved data. Record the actual evidence in the release test record. This check is incremental to the current candidate and does not claim a full-history audit.

## Triggered Deep Audit

Run a deep audit only when triggered by a privacy-boundary, workflow, packaging, secret-handling, telemetry/upload, history-rewrite, repository-security-setting change, a suspected leak, or explicit user request.

Scope the audit to the trigger and inspect relevant Git history, historical Actions logs/artifacts, PRs, issues, comments, repository security settings, and secret rotation status. Record the trigger, scope, findings, remediation, and result. A deep audit is not a routine substitute for the per-release Incremental Privacy Check.

## Local Service Package Contract

The local service zip must include these scripts:

- `Install NxJob Local Service.bat`
- `Start NxJob Local Service.bat`
- `Check NxJob Local Service.bat`
- `Status NxJob Local Service.bat`
- `Stop NxJob Local Service.bat`
- `Uninstall NxJob Local Service.bat`
- `scripts/install-local-service.ps1`
- `scripts/install-local-service.bat`
- `scripts/start-local-service.ps1`
- `scripts/start-local-service.bat`
- `scripts/check-health.ps1`
- `scripts/check-health.bat`
- `scripts/status-local-service.ps1`
- `scripts/status-local-service.bat`
- `scripts/stop-local-service.ps1`
- `scripts/stop-local-service.bat`
- `scripts/uninstall-local-service.ps1`
- `scripts/uninstall-local-service.bat`

The scripts are the Windows service startup adapter for MVP. They may later be replaced or wrapped by MSI, NSIS, Inno Setup, or another installer, but core local-service business code should stay platform-neutral.
