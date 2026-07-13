# Hooks Playbook

Hooks are optional enhancements around worker execution. They do not replace the wrapper.

The wrapper launches only a Controller-approved, default-off auxiliary worker. Wrapper or hook output cannot satisfy mandatory GPT-5.4 Implementer, Reviewer, or Release gates.

## Wrapper Primary

Use the wrapper as the primary control surface for:

- packet ingestion;
- model alias and provider resolution;
- artifact path setup;
- bounded execution;
- exit code normalization;
- final status emission.

Hooks may add convenience, but the system must still operate when hooks are absent or partially disabled.

Primary means the wrapper alone must still be sufficient to:

- run a dry-run safely;
- redact prompt text from status, logs, and dry-run previews;
- write trustworthy final status;
- identify whether hooks were absent, partial, or broken.

## Why Hooks Are Secondary

Hooks are useful for:

- writing lightweight heartbeats;
- adding local timestamps;
- emitting compact summaries;
- validating artifact shape before exit.

Hooks are risky as the primary mechanism because they can be:

- shell-specific;
- harder to debug than the wrapper;
- sensitive to environment drift;
- noisy if they write too much token-visible output.

## Hook Caveats

- Do not put secrets, API keys, cookies, browser profiles, or production data into hook output.
- Do not make hooks the only place where critical status is written.
- Do not rely on hooks for full-log tailing or dashboard streaming.
- Do not let hook failure silently turn a blocked worker into a completed worker.
- Do not let hook failure overwrite wrapper-owned final status.
- Keep terminal reports exclusive: `completed` uses only `implementation_report.md`; `stalled`, `blocked`, or `failed` uses only `failure_report.md`.
- Keep hook output small and structured.

## Headless Prompt Privacy Caveat

The first wrapper uses `claude -p` because it is the stable headless entry point available to the harness. The wrapper redacts prompt content from `worker_log.ndjson`, `worker_status.json`, and dry-run output, but the prompt text can still exist as a local process argument while the worker is running.

Treat task prompts as approved task packets, not secret containers:

- Do not put API keys, cookies, browser profiles, generated resumes, real application records, or other secrets in the task prompt.
- Do not put any secret-bearing material into headless prompt text just because the wrapper later redacts its own artifacts.
- Put sensitive references behind allowed local paths and let the controller decide whether the worker may access them.
- If a future Claude Code CLI mode supports stdin or prompt-file execution with equivalent behavior, prefer it over command-line prompt text.

## Recommended Pattern

1. Wrapper creates task packet context and artifact paths.
2. Worker runs.
3. Hooks optionally append small structured signals.
4. Wrapper validates final artifacts and returns normalized status.

If a hook fails, classify it under `artifact_contract` or `environment_runtime` and continue only if the wrapper can still produce a trustworthy final status.

## Dry-Run Verification

`scripts/run_claude_worker.ps1` requires an approved task id and prompt file even in `-DryRun` mode. This is intentional: the dry-run path still verifies that runtime artifacts stay inside `.agent_tasks/<TaskId>/` and remain ignored by Git.

Use the complete command form:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_claude_worker.ps1 -TaskId verify-workflow-stabilization -PromptFile .agent_tasks\verify-workflow-stabilization\prompt.txt -ModelTier flash -WorkerRole "Auxiliary Worker" -ReasoningEffort medium -DryRun
```

Do not treat `scripts\run_claude_worker.ps1 -DryRun` without a task id and prompt file as a valid check.

## Read-Only Hook Checks

Repository check scripts such as `scripts/check_hooks.ps1` should stay read-only:

- inspect whether hook configuration exists;
- report parseability and configured hook keys;
- avoid rewriting settings;
- avoid creating runtime artifacts outside the active task packet.
