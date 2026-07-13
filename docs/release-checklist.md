# NxJob Release Checklist

## Entry Conditions

- NxJob is already public; this checklist governs every versioned development build, pre-release, and stable release.
- Formal release work uses a dedicated release-candidate worktree and the sequence below.
- The intended SemVer version and release type (`stable` or `pre-release`) are explicit.
- The candidate commit is identified, scoped changes and mandatory gates are complete, and no real private data is used for testing.
- README, LICENSE, install documentation, release notes, and version differences are current where applicable.

## Required Agent Sequence

1. GPT-5.4 / Medium Implementer completes release-document or release-code changes and applicable checks.
2. GPT-5.4 / Medium Release Agent builds and records artifact, install, version, and privacy evidence.
3. Independent GPT-5.6 Terra or Sol / High Reviewer inspects the diff and evidence and runs risk-targeted checks.
4. Controller records a release recommendation.
5. User gives explicit authorization before any remote publication action.

No role may collapse this sequence or treat missing Reviewer evidence as approval.

## Version and Artifact Consistency

Run the release build with one explicit version input:

```powershell
.\scripts\package\build-release.ps1 -Version <version>
```

The `-Version <version>` argument is the formal version source. It must agree with version metadata, package contents, artifact names, `release-manifest.json`, `release-test-record-<version>.md`, release-notes folder, later tag `v<version>`, and GitHub Release identity.

Required artifacts remain:

- `NxJob-<version>.zip`;
- `nxjob-local-service-<version>.zip`;
- `nxjob-extension-<version>.zip`;
- `release-manifest.json`;
- `release-test-record-<version>.md`.

The manifest commit, candidate commit, and eventual tag commit must match.

## Automated and Manual Validation

- Record the exact build and validation commands and their output evidence.
- Run all automated checks required by the build, release validator, affected specialized documents, and current change risk.
- Test the Windows package with an install path containing spaces.
- Record install, start, health, status, stop, and uninstall results.
- Load the extension package and smoke-test every affected user workflow.
- Record desktop/local-service and browser-extension data-source boundaries.
- Every check is `PASS`, `FAIL`, `BLOCKED`, or `N/A`; every `N/A` includes a reason.

## Incremental Privacy Check for Every Release

Every release performs an Incremental Privacy Check against the current candidate:

- inspect the current tracked tree and release diff for secrets, real resumes, generated resumes, databases, PromptLogs, recruiter replies, application records, and private local paths;
- inspect all release artifacts for `private/`, `.nxjob/`, local databases, PromptLogs, generated resumes, credentials, caches, `.git/`, and user-specific configuration;
- inspect current workflow/Actions output and user-visible logs/errors for private values or paths;
- confirm packaged assets, manifest, test record, and release notes contain only approved public evidence;
- confirm README and release copy direct ordinary users to `NxJob-<version>.zip`, not automatic source archives.

Record evidence in the release test record for every release.

## Triggered Deep Audit

A Triggered Deep Audit is required only when the release changes privacy boundaries, workflows, packaging, secret handling, telemetry/upload behavior, history, repository security settings, or when a leak is suspected or the user requests it.

When triggered, inspect the relevant full Git history, historical Actions logs/artifacts, PRs, issues, comments, repository security settings, and secret rotation status. Record the trigger, scope, findings, remediation, and result. Do not claim a deep audit when only the incremental candidate check ran.

## Stable vs Pre-release Decision

- A stable release requires all applicable automated and manual checks, completed release evidence, Incremental Privacy Check, required deep audit if triggered, independent Reviewer pass, and Controller recommendation.
- Missing, failed, blocked, or partially recorded applicable checks cannot support a stable release.
- Incomplete evidence permits only a development build or an explicitly marked pre-release.
- `N/A` is acceptable only with a concrete reason showing why the check does not apply.

## Local Release Folder

Build and validate artifacts under:

```text
releases/<version>/
```

This folder is the source for later GitHub Release uploads. Non-technical users receive `NxJob-<version>.zip`, not repository source archives or development scripts.

## User Authorization Before Publication

Tag creation, push, PR create/update, GitHub Release create/update, and artifact upload are remote writes requiring explicit user authorization. Local readiness or Controller recommendation does not grant publication permission. Approval for one action does not imply approval for another.
