# Release Hardening

M9 improves the MVP packaging flow without changing NxJob's product behavior.

## Scope

- Keep Phase 1 REST-only.
- Keep private data out of release artifacts.
- Keep Windows-specific behavior inside packaging and service startup scripts.
- Improve the local-service package from a basic zip into an operational package with install, start, status, stop, health check, and uninstall scripts.
- Provide root-level `.bat` launchers so non-technical users can double-click common service actions without opening a command line.
- Validate generated artifacts before a release is considered usable.

## Release Artifact Contract

Each release folder should contain:

- `nxjob-local-service-<version>.zip`
- `nxjob-extension-<version>.zip`
- `release-manifest.json`
- `release-test-record-<version>.md`

Run:

```powershell
.\scripts\package\build-release.ps1 -Version <version>
```

The build script runs automated checks, builds both packages, writes the release manifest, writes a release test record, and validates the artifacts.

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
