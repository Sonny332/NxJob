# Release Test Record

Use this evidence template for every versioned build. Blank or partially completed records cannot support a stable release.

## Evidence Format

Every check records exactly one status with concrete evidence or reason:

- `PASS — <evidence>`
- `FAIL — <evidence>`
- `BLOCKED — <reason>`
- `N/A — <reason>`

An empty field is not `N/A`. Do not report checks that were not run as passing.

## Release Identity

- Explicit version input (`build-release.ps1 -Version <version>`):
- Commit:
- Release type (`stable` or `pre-release`):
- Date:
- Release Agent:
- Candidate worktree/branch:

## Exact Commands

- Build command:
- Build result:
- Validation command:
- Validation result:
- Additional automated commands and results:

## Artifacts

- `NxJob-<version>.zip`:
- `nxjob-local-service-<version>.zip`:
- `nxjob-extension-<version>.zip`:
- `release-manifest.json`:
- `release-test-record-<version>.md`:
- Metadata, artifact, manifest, record, notes-folder, and version-input agreement:
- Candidate commit and manifest commit agreement:

## Automated Validation

- Shared schema check:
- Extension typecheck:
- Extension build:
- Local-service project pytest wrapper:
- Release validator:
- Other applicable checks:

## Windows Local-Service Package

- Path-with-spaces test path:
- Path-with-spaces result:
- Install result:
- Start result:
- Health result:
- Status result:
- Stop result:
- Uninstall result:
- Root-level launcher result:

## Extension and Workflow Smoke Tests

- Extension package load:
- Analyze Sponsorship affected flow:
- Tailor Resume affected flow:
- Fill Form Answer affected flow and confirmation boundary:
- Application/outcome affected flow:
- Other affected workflow:

## Privacy Evidence

- Incremental Privacy Check result:
- Current tree and release diff evidence:
- Artifact-content evidence:
- Current Actions/workflow output evidence:
- User-visible log/error evidence:
- Deep audit trigger (`none` or reason):
- Triggered Deep Audit scope/result (`N/A — no trigger` or evidence):

## Review and Publication

- Independent Reviewer decision:
- Controller recommendation:
- Remote publication authorization status:
- Authorized actions, if any:
- Tag/push/GitHub Release/upload status:

## Version Differences

- Added:
- Changed:
- Fixed:
- Known limits:

## Stable Release Decision

- All applicable automated checks complete:
- All applicable manual checks complete:
- All `N/A` entries include reasons:
- Evidence record complete:
- Final release decision (`stable`, `pre-release`, or development build):
