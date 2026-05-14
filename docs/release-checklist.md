# NxJob Release Checklist

NxJob version numbers follow `docs/versioning.md`.

This checklist applies when preparing a versioned local or GitHub release. Ordinary development batches should not run the full release process unless they are becoming a published package.

Before every release:

- README is current.
- LICENSE exists and matches the intended distribution model.
- If the release will make the repository public, complete the Public Repository Readiness Gate below before changing visibility.
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

## Public Repository Readiness Gate

Complete this gate before changing a private NxJob repository to public:

- Tracked files have been scanned for real master resumes, generated resumes, API keys, local SQLite databases, PromptLogs, recruiter replies, real application records, and private local paths.
- Git history has been scanned for high-risk secret and resume indicators. If a real secret or private resume appears in history, stop and rotate the secret or clean history before publishing.
- GitHub Actions history, logs, artifacts, PRs, issues, and comments have been checked for sensitive paths, tokens, API keys, real resume content, real JD content, real emails, or private job-search data.
- Release assets have been inspected and do not contain `private/`, `.nxjob/`, local databases, PromptLogs, generated resumes, `.git/`, caches, or user-specific config.
- README points ordinary users to `NxJob-<version>.zip` and does not present GitHub's automatic source archive as the normal install path.
- Repository About text, description, topics, and website link are accurate and do not imply unsupported automation such as bulk applying or automatic submission.
- Default branch, release tag, GitHub Release assets, and `release-manifest.json` all point to the same release commit.
- Secret scanning and push protection are enabled, or the required manual GitHub Security settings are recorded before publishing.
- `main` branch protection has been considered. At minimum, direct accidental pushes to `main` should be avoided after the repository is public.
- GitHub Actions permissions and fork pull-request settings have been reviewed for public-repository exposure.

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

