# NxJob Versioning

NxJob uses Semantic Versioning.

Format:

```text
MAJOR.MINOR.PATCH
```

Example:

```text
0.2.1
```

Git tags should use a `v` prefix:

```text
v0.2.1
```

## Meaning

`MAJOR` changes when NxJob makes a broad product, architecture, or compatibility change.

Examples:

- Database changes that cannot be migrated safely.
- Local REST architecture changes to MCP-first.
- Installer or runtime model changes that require a different user setup.
- Large workflow boundary changes.

`MINOR` changes when NxJob adds user-visible functionality while keeping compatibility.

Examples:

- New plugin UI surfaces such as Side Panel.
- New workflow buttons.
- New REST endpoints.
- Master Resume Builder.
- Real AI provider integration.
- Email tracking or interview-prep flows.

`PATCH` changes when NxJob fixes bugs or hardens existing behavior without changing the main feature set.

Examples:

- Local service 500 fixes.
- Windows path quoting fixes.
- Content script connection fallback.
- Release packaging cleanup.
- Test-only changes.
- Documentation corrections that do not change user-facing behavior.

## MVP 0.x Rule

NxJob is still pre-1.0 during MVP.

Use `0.MINOR.PATCH` until the product is stable enough for a first non-technical user release.

Recommended interpretation:

- `0.1.x`: first installable MVP line.
- `0.2.x`: Side Panel, workflow cache, and setup UI line.
- `0.3.x`: Master Resume Builder or other larger workflow additions.
- `1.0.0`: first stable release where install, local service, extension, privacy boundaries, and core workflows are considered dependable for normal users.

## Pre-release Labels

Pre-release labels are optional.

Allowed examples:

```text
0.2.0-alpha.1
0.2.0-beta.1
0.2.0-rc.1
```

Use them only when publishing test builds that should not replace the latest stable release.

## Release Decision Rules

When multiple changes are included in one release, choose the highest required bump.

Examples:

- One new feature plus two bug fixes: bump `MINOR`.
- Only bug fixes: bump `PATCH`.
- Any incompatible data or setup change: bump `MAJOR`.

Every released version must have:

- A matching Git tag.
- A local release folder under `releases/<version>`.
- A `release-manifest.json` whose `commit` matches the tagged commit.
- A completed or partially completed `release-test-record-<version>.md`.
- GitHub Release assets built from that same local release folder.

## Current Recommended Mapping

Historical packages may not perfectly follow this rule because the policy was adopted after early MVP development.

Going forward:

- M10 Side Panel and workflow cache should be treated as a `MINOR` release.
- Content script fallback and release package cleanup should be treated as `PATCH` releases under the same minor line.
