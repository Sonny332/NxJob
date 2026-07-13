# NxJob Versioning

NxJob uses Semantic Versioning in `MAJOR.MINOR.PATCH` form. Git tags use the matching `v<version>` form.

## SemVer Meaning

- `MAJOR`: incompatible product, architecture, data, runtime, installer, or workflow-boundary change.
- `MINOR`: backward-compatible user-visible capability.
- `PATCH`: bug fix, hardening, packaging correction, test-only change, or non-user-visible documentation correction.

NxJob remains on `0.MINOR.PATCH` during MVP. Choose the highest bump required by all changes in the release batch.

## Ordinary Development

Ordinary untagged changes do not bump the version. Batch small fixes, provider presets, documentation corrections, and tests until a formal versioned build or release is intentionally prepared.

## Pre-release Labels

Use SemVer pre-release labels for test builds that must not replace the latest stable release:

```text
0.8.0-alpha.1
0.8.0-beta.1
0.8.0-rc.1
```

An explicit pre-release may have incomplete evidence, but every completed check must still be recorded honestly. It must not be represented as stable.

## Formal Version Input

The single formal version input is the explicit build argument:

```powershell
.\scripts\package\build-release.ps1 -Version <version>
```

The input version must match version metadata, package contents, artifact names, `release-manifest.json`, `release-test-record-<version>.md`, release notes folder, eventual tag `v<version>`, and GitHub Release identity.

Do not infer a formal version from the current tag, folder name, manifest, or source metadata. Those are outputs or consistency surfaces checked against the explicit input.

## Release Evidence

- Every stable release has a completed release-test record.
- A blank or incomplete record is allowed only for a development build or explicitly identified pre-release.
- Every check records `PASS`, `FAIL`, `BLOCKED`, or `N/A`; every `N/A` includes a reason.
- A stable release requires all applicable automated and manual checks, required privacy evidence, independent Reviewer pass, and Controller recommendation.
- Missing applicable evidence cannot support a stable release.

## Tag and Publication Order

1. Select the SemVer version and release type.
2. Run `build-release.ps1 -Version <version>` and the required validation.
3. Complete the release-test record and review gates.
4. Confirm metadata, artifacts, manifest, record, notes folder, and candidate commit agree.
5. Create tag `v<version>` only after build and validation pass and the required user authorization is given.
6. Push, GitHub Release creation/update, and artifact upload occur only after explicit user authorization.

The tag commit, manifest commit, artifact source commit, and GitHub Release must agree. Authorization for one remote action does not authorize another.

## Historical Versions

Historical MVP packages may not perfectly follow this policy because it was adopted after early releases. Do not rewrite old release identities merely to match the current process; apply these rules to new formal builds and releases.
