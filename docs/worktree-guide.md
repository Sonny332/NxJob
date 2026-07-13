# NxJob Worktree Guide

## Purpose

Worktrees provide isolation when an approved hard trigger applies. They are not created merely because a task uses an Implementer or Reviewer. Complete triggers and Git permissions are defined in `docs/development-governance.md`.

## Mandatory Triggers

Use an independent worktree for:

- Sol-level architecture or major-impact changes;
- schema/database migration or existing-data conversion;
- a formal release candidate;
- parallel Implementers or mutually exclusive implementation experiments;
- changes across two or more independent runtime subsystems;
- work not safely recoverable with one revert;
- an unsafe-to-share dirty workspace;
- an explicit user request.

A worktree is not mandatory for Controller-direct work, read-only investigation, a local single-module bug, documentation cleanup, a local visual fix, or a bounded test adjustment unless another trigger applies.

## Create a Worktree

Run from the main worktree:

```powershell
git status -sb
git fetch origin
git log --oneline HEAD..origin/main
git worktree add '..\NxJob-worktrees\agent-governance' -b codex/agent-governance-optimization
```

`fetch` and read-only remote comparison are autonomous. If `HEAD..origin/main` lists commits, stop and obtain explicit user approval before `pull`, merge, or rebase. Do not update the local branch automatically.

Before creation, also confirm that the current workspace does not contain user changes that would be mixed into the task and that the proposed worktree path and branch are not already in use.

## Work in the Isolated Checkout

```powershell
Set-Location '..\NxJob-worktrees\agent-governance'
git status -sb
```

Keep one coherent goal per branch. Do not create nested worktrees inside the repository. Preserve unrelated user changes and keep generated or sensitive files out of Git.

## Qualified Local Commit

A local commit is allowed only after scoped work is complete, mandatory gates and checks have passed, and the diff contains no unrelated or sensitive files. Stage an explicit file list, never a repository-wide wildcard:

```powershell
git add 'docs/worktree-guide.md'
git diff --cached --check
git commit -m "docs: optimize agent governance"
```

Report the commit hash and that it remains unpushed.

## After User Authorization

Remote writes require explicit user approval. This includes `push`, tag creation, PR creation or update, GitHub Release creation or update, and artifact upload.

After approval for the specific push:

```powershell
git push -u origin codex/agent-governance-optimization
```

Approval for one remote action does not imply approval for another. `pull`, merge, and rebase also require explicit user approval even though they update local state.

## Cleanup

Before removing a worktree, verify its resolved absolute path and require one of these conditions:

1. The branch changes are merged.
2. The branch changes are preserved in local commits and the user explicitly approves removal.
3. The user explicitly approves discarding the work.

The branch does not need to be pushed before removal. Never infer permission to discard from a clean-looking status or a failed remote operation.

After the applicable condition and required approval are confirmed, run cleanup from the main worktree with the exact intended path:

```powershell
git worktree remove '..\NxJob-worktrees\agent-governance'
git worktree prune
```

Deleting an unmerged branch or worktree requires explicit user approval. Do not use forced removal unless the user explicitly authorizes discarding the identified work.

## Release Worktrees

- Use a dedicated worktree for a formal release candidate.
- Build only from a clean, reviewed checkout and keep artifacts under `releases/<version>`.
- Confirm the release manifest commit and explicit version identity before recommending publication.
- Tag, push, GitHub Release, and artifact upload remain separate user-authorized remote writes.
- Do not publish from an active feature worktree.
