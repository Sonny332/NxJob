# NxJob Development Governance

NxJob uses Agent Collaboration Model as the default development workflow. Personal MVP priorities remain valid as product and velocity context, but they do not override mandatory agent gates, review requirements, or other workflow rules defined under the collaboration model.

## Rule Priority

When rules overlap or conflict, use this order:

1. Safety boundaries: no automatic submission, no CAPTCHA bypass, no bulk scraping, and no no-confirmation mass applying.
2. Privacy boundaries: real resumes, generated resumes, application records, local databases, API keys, and full PromptLog contents must stay out of GitHub, release packages, ordinary logs, and plugin-visible errors.
3. Release quality: versioning, release checklist, installer validation, manifest/tag alignment, and release test records stay strict when preparing a versioned release.
4. Agent Collaboration Model and mandatory agent gates: default workflow, required roles, review gates, handoff reporting, and exception handling for sub-agent failures.
5. Personal MVP and lightweight workflow preferences: milestone, worktree, PR, and process-cost decisions should stay proportional to risk, but cannot weaken mandatory agent gates.
6. Documentation style and process preferences can be changed when they improve MVP velocity without conflicting with the higher-priority rules above.

## Agent Collaboration Model

Agent Collaboration Model is the default NxJob workflow rule set.

- The main agent / controller owns goal judgment, scope control, task splitting, acceptance criteria, and merge/release decisions.
- Sub-agents are required by default unless the user explicitly says the current task does not need sub-agents.
- The default NxJob development lane is:
  - PM / Controller coordinates scope, sequencing, acceptance, and final handoff.
  - Implementer / Coding Agent handles implementation, debugging, code mapping, tests, docs, and rules changes.
  - Reviewer / Evaluator Agent reviews risk before completion claims, PR handoff, merge readiness, or release readiness.
- Planner / Architect is used for new features, broad refactors, schema/architecture decisions, or release planning.
- Do not let the controller silently absorb implementation and review work when sub-agents are required.
- Small one-line fixes may bypass sub-agents only when the user explicitly allows it and the task is outside all mandatory gate categories.

Recommended roles for NxJob's current scale:

| Role | When to use | Suggested model / effort |
| --- | --- | --- |
| PM / Controller | Default orchestration, scope, acceptance, and merge decisions | GPT-5.5 Thinking / Medium-High |
| Planner / Architect | New feature, architectural change, large refactor, or release planning | GPT-5.5 Thinking / Medium-High |
| Implementer | Normal code changes and tests | GPT-5.1 / Medium |
| Reviewer / Evaluator | High-risk change, PR merge decision, or release readiness | GPT-5.5 Thinking / Medium |
| Code Mapper | Unknown structure, broad cross-module impact, or refactor preparation | GPT-5 mini / Low |
| Docs Agent | Focused documentation cleanup | GPT-5 mini / Low-Medium |
| Test Agent | Focused verification or regression test expansion | GPT-5 mini / Low-Medium |
| Release Agent | Versioned release preparation and package validation | GPT-5.1 / Medium |
| Resume Quality Agent | Resume output quality evaluation and prompt/rule review | GPT-5.5 Thinking / Medium-High |
| Form Answer Agent | Form-answer drafting quality checks | GPT-5 mini / Low-Medium |

These model choices are recommendations, but the role workflow is mandatory by default. Prefer the minimum required sub-agent set instead of a large agent team.

### Mandatory Agent Gates

For any task involving business code, debugging, tests, release scripts, schema, plugin UI, privacy boundaries, packaging, or versioned release work:

1. PM / Controller must assign implementation or debugging to an Implementer / Coding Agent.
2. PM / Controller must obtain a Reviewer / Evaluator pass before claiming completion.
3. If a sub-agent tool cannot use the requested model with full-history context, PM should retry with a compact task prompt and explicit model selection instead of dropping model requirements silently.
4. If Reviewer / Evaluator times out or fails, PM must not treat review as passed. PM must retry with a narrower review task, replace the reviewer, or report the missing review as a blocker.
5. Exception handling under "Sub-agent Failure Handling" may unblock a specific blocker, but it does not remove the default sub-agent requirement or turn a missing Reviewer / Evaluator pass into approval.
6. Final handoff must list each sub-agent used or skipped, including role, exact model version, reasoning effort, status, and whether the output was used.
7. If the tool cannot confirm the exact model version for a required gate, report `unknown, not acceptable for required gate` and retry with explicit model selection instead of treating the gate as satisfied.

The only default exception is a user-explicit instruction such as "this task does not need sub-agents" or "do this directly without sub-agents."

### Sub-agent Failure Handling

Sub-agent failure handling is exception logic under Agent Collaboration Model. It cannot outrank or replace mandatory agent gates.

- If a sub-agent fails, times out, or returns unusable output, record:
  - assigned role and task;
  - exact model version and reasoning effort, or `unknown, not acceptable for required gate` when the tool cannot confirm it for a required gate;
  - failure mode;
  - root cause hypothesis;
  - mitigation used or proposed.
- For a first occurrence, include the summary in the handoff and, when useful, add a development memory note.
- If the same class of sub-agent failure happens twice or more, add the mitigation to this governance document.
- If the same sub-agent or same class of sub-agent fails 3 consecutive times on the same task and same blocker, PM / Controller may decide that PM Agent directly resolves only that blocker to restore progress.
- This 3-failure bypass is scoped to the current blocker only. After that blocker is resolved, PM / Controller must return the work to the required sub-agent workflow at the next viable step, including implementation or review gates that still apply.
- Do not wait indefinitely. Use bounded waits, then retry with a narrower prompt, replace the agent, or stop and report the blocker.
- Do not close a required Reviewer / Evaluator and then claim completion unless a replacement review path has passed or the missing review is explicitly called out as incomplete.

## Personal MVP Development Context

This section is product and speed context for NxJob. It is not the default workflow mode and must not be used to override Agent Collaboration Model or mandatory gates.

Development priorities:

1. Reduce friction in real job-search and application workflows.
2. Complete runnable, testable, end-to-end loops before expanding process.
3. Avoid splitting small tasks into too many milestones, worktrees, PRs, or reviews.
4. Keep engineering quality, but scale the process cost to the project size and risk.

## Milestone Granularity

Milestones should represent user-visible product progress, not internal implementation steps.

Prefer 5-6 major milestone families:

- Core Capture & Local Service
- Sponsorship & Decision Aid
- Resume Tailor Usable Loop
- Form Answer & Application Tracking
- Release & Daily Use Hardening
- Post-MVP Learning / Success Feedback

Do not create a milestone for a single UI text change, test fix, schema field, provider preset, small bug fix, or documentation correction unless it carries unusual risk.

## Worktree Usage

Worktrees are for isolation, not the default unit of work.

Use a worktree for:

- Large feature development.
- High-risk refactors.
- Database or schema migrations.
- Release candidates.
- Parallel experiments.
- Changes with broad rollback risk.

Do not default to a worktree for:

- Small bug fixes.
- Copy or documentation changes.
- Small UI adjustments.
- Small test fixes.
- Single-file low-risk changes.

If a task does not meet the worktree threshold, use the current active branch or a lightweight branch strategy.

## PR Granularity

A PR should represent one of:

- A user-visible value unit.
- A high-risk technical change.
- A release candidate.
- An architecture change that needs explicit review.

Small changes can be batched into the current development unit. At handoff, report:

- Changed files.
- Tests or checks run.
- Risk notes.
- Whether a PR is necessary.

Do not open a PR by default unless the user asks, or the task clearly fits the PR threshold.

## Anti-over-fragmentation

Before splitting a task, confirm the split reduces risk.

Split only when:

- Subtasks can be independently tested.
- Subtasks have independent user value.
- Subtasks have independent rollback risk.
- Subtasks involve different risk domains, such as database migration versus UI copy.
- The user explicitly asks for phased execution.

If multiple edits serve the same user goal, prefer one coherent implementation batch.

## Token Efficiency

Avoid unnecessary context and planning overhead:

- Do not repeat already established NxJob background.
- Do not write long implementation plans for low-risk changes.
- Do not restate stable MVP boundaries unless they affect the decision.
- Do not rescan unrelated files.
- Read only the smallest relevant file set before editing.

Required exception: before changing architecture, schema, privacy, release, worktree, agent, or governance rules, read the relevant rule documents first.

## Long-running Task and Repeated-error Handling

Long-running agent or command work must have an explicit timeout and fallback.

- Do not wait indefinitely for a sub-agent, test command, packaging command, or GitHub operation.
- For normal checks, use short timeouts first. For expensive commands, state why the longer timeout is needed.
- If a sub-agent does not return useful status within the timeout, stop waiting and inspect local state. If the sub-agent was optional, close it or continue with the controller. If the sub-agent was required, retry with a narrower task, replace it, or report the missing gate as a blocker.
- If Codex Desktop appears stuck but no command output is changing, first read the current terminal/session state or switch away and back once to refresh the UI. Treat that as a UI recovery step, not as proof the underlying task is still working.
- When sub-agents are used, the controller must keep a short list of active agents, their assigned role, and the last useful result. Do not let a completed implementation wait indefinitely for a review agent; use one bounded wait, then retry, replace, or report a blocked review gate. A required review timeout is not equivalent to approval.
- When the right-side branch details or handoff summary lists sub-agents, show more than the nickname. Include the assigned role, exact model version, reasoning effort, and current state. If the exact model cannot be confirmed for a required gate, report `unknown, not acceptable for required gate` and retry with explicit model selection. Use a compact format such as `Jason — Reviewer / Evaluator — GPT-5.5 Thinking / Medium — closed after timeout`.
- If a command fails twice with the same class of error, stop repeating it and switch to systematic debugging: identify the failing layer, form one hypothesis, and test that hypothesis with the smallest command.
- On Windows, do not ask sub-agents or Claude workers to run raw `python -m pytest`. Use `scripts/run_pytest.ps1` or `scripts/test-local-service.ps1` so pytest temp directories are created through the repository harness under the Windows temp folder rather than Python 3.14's restrictive Windows `0o700` mkdir path or the repository's D-drive ACL.
- If a command appears to hang, check whether useful work has already completed before retrying. Record the last successful command and avoid rerunning broad suites unnecessarily.
- At handoff, report any interrupted or closed sub-agents, known background processes, and whether the worktree is clean.

Default timeout guidance:

- Quick file, Git, type, and unit-test checks: 30-120 seconds.
- Local service startup, packaging, or release validation: 2-10 minutes with progress updates.
- Sub-agent review or implementation: wait once with a bounded timeout. If the sub-agent is optional, poll or close if no status is returned. If the sub-agent is required, retry with a narrower task, replace it, or report the gate as blocked.
- Anything still running after 30 minutes requires an explicit status update and a decision to continue, close, or replace the task path.

## Windows Path Handling

Windows paths with spaces are expected in this project and must be treated as a normal test case.

- In PowerShell, prefer `-LiteralPath` for filesystem paths and quote path values with single quotes in commands and documentation examples.
- In Python, Node, and PowerShell process launches, pass path arguments as argument arrays or structured parameters. Do not build one shell string that embeds unescaped path values.
- When testing packaging, local service startup, generated resumes, or user-selected output folders, include at least one path under a profile name with spaces, such as `C:\Users\Sonny Shen\...`.
- If a command fails only when a path contains spaces, treat it as a bug in quoting or process invocation, not as a user environment issue.

## Existing Rule Handling

When a similar rule already exists, merge instead of duplicating.

- Keep the clearer and more specific wording.
- Preserve stricter safety, privacy, and release requirements.
- Rewrite over-enterprise workflow rules when they do not protect safety, privacy, or release quality.
- If a conflict is unclear, list it for user confirmation instead of deleting a key rule.
