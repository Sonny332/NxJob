# NxJob Release Checklist

NxJob version numbers follow `docs/versioning.md`.

Before every release:

- README is current.
- LICENSE exists and matches the intended distribution model.
- Version is updated according to SemVer.
- Local `releases/<version>` artifacts are generated from the exact release commit.
- `release-manifest.json` commit matches the Git tag commit.
- Git tag `v<version>` is created.
- Release notes describe user-facing changes and known limits.
- One-click Windows package `NxJob-<version>.zip` is generated.
- Windows local-service installer is generated.
- Browser extension package is generated.
- `release-manifest.json` is generated.
- `release-test-record-<version>.md` is generated.
- `scripts/package/validate-release.ps1` passes.
- `docs/install-windows.md` is current.
- `docs/release-test-record.md` is copied or filled for this release.
- Local service install/start/status/stop/uninstall scripts are present in the package.
- Root-level `.bat` launchers are present for one-click install/start/status/stop/uninstall.
- GitHub release description tells users to download `NxJob-<version>.zip`, not `Source code (zip)`.
- Installer test result is recorded.
- Version differences from the previous release are recorded.
- Desktop/local-service data source and browser-extension data source boundaries are clear.

MVP should present installers and packaged artifacts to non-technical users, not source code or development scripts.

## Local Release Folder Rule

Every version change must update the local release folder before GitHub Release publication.

Required folder:

```text
releases/<version>/
```

Required files:

- `NxJob-<version>.zip`
- `nxjob-local-service-<version>.zip`
- `nxjob-extension-<version>.zip`
- `release-manifest.json`
- `release-test-record-<version>.md`

The GitHub Release should upload these files from `releases/<version>`.
Do not upload GitHub's automatic source archive as the user-facing installer.

