# NxJob Worktree Guide

## Goal

NxJob uses worktrees when a task needs isolation. Worktrees are not the default unit for every small change.

For the broader development process, see `docs/development-governance.md`.

Recommended layout:

```text
D:\Codex\NxJob                  # main worktree, kept close to origin/main
D:\Codex\NxJob-worktrees\m2     # branch codex/m2-local-service-core
D:\Codex\NxJob-worktrees\m3     # branch codex/m3-extension-mvp
```

## Daily Flow

From the main worktree:

```powershell
git status -sb
git pull --ff-only
git worktree add ..\NxJob-worktrees\m2 -b codex/m2-local-service-core
```

Work inside the milestone worktree:

```powershell
cd ..\NxJob-worktrees\m2
git status -sb
```

Commit and push from that worktree:

```powershell
git add -A
git commit -m "Implement local service core"
git push -u origin codex/m2-local-service-core
```

After the branch is merged:

```powershell
cd D:\Codex\NxJob
git pull --ff-only
git worktree remove ..\NxJob-worktrees\m2
git branch -d codex/m2-local-service-core
git worktree prune
```

## Rules

- Keep `D:\Codex\NxJob` on `main`.
- Use worktrees for large features, high-risk refactors, database or schema migrations, release candidates, parallel experiments, and changes with broad rollback risk.
- Do not default to a worktree for small bug fixes, copy changes, small UI fixes, small test fixes, documentation cleanup, or single-file low-risk changes.
- If a task does not need worktree isolation, use the current active branch or a lightweight branch strategy.
- When using a worktree, use one branch per milestone, focused feature, or release candidate.
- Do not create nested worktrees inside the main repo directory.
- Before starting a new worktree, run `git pull --ff-only` in main.
- Before deleting a worktree, confirm its branch is pushed or merged.
- Use branch names like `codex/m2-local-service-core`.

## Release Worktrees

GitHub Release publication can be done from Codex CLI, but only from a clean release-ready checkout.

Recommended rule:

- Do not publish a GitHub Release from an active feature worktree.
- Use `main` after the release PR is merged, or create a dedicated release worktree from the tagged commit.
- Confirm `git status -sb` is clean before building, tagging, or uploading assets.
- Build local artifacts into `releases/<version>` before publishing.
- Confirm `release-manifest.json` commit matches tag `v<version>`.
- Upload release assets from `releases/<version>`, not from source folders.

This keeps feature-branch state, generated artifacts, and GitHub Release assets from drifting apart.
