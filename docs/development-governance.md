# NxJob Development Governance

NxJob is a personal MVP project. Development process should reduce real job-application friction instead of creating enterprise-level ceremony.

## Rule Priority

When rules overlap or conflict, use this order:

1. Safety boundaries: no automatic submission, no CAPTCHA bypass, no bulk scraping, and no no-confirmation mass applying.
2. Privacy boundaries: real resumes, generated resumes, application records, local databases, API keys, and full PromptLog contents must stay out of GitHub, release packages, ordinary logs, and plugin-visible errors.
3. Release quality: versioning, release checklist, installer validation, manifest/tag alignment, and release test records stay strict when preparing a versioned release.
4. Workflow rules: worktree, PR, milestone, and review process should be lightweight and proportional to risk.
5. Documentation style and process preferences can be changed when they improve MVP velocity.

## Personal MVP Development Mode

Development priorities:

1. Reduce friction in real job-search and application workflows.
2. Complete runnable, testable, end-to-end loops before expanding process.
3. Avoid splitting small tasks into too many milestones, worktrees, PRs, or reviews.
4. Keep engineering quality, but scale the process cost to the project size and risk.

## Agent Collaboration Model

Use a lightweight controller-led model.

- The main agent / controller owns goal judgment, scope control, task splitting, acceptance criteria, and merge/release decisions.
- Sub-agents are used only when they create clear value.
- Do not start planning, implementation, review, and code-mapping agents for every small task.
- Small bug fixes, copy changes, test fixes, and low-risk documentation updates should normally stay with the controller or a single implementer.

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

These are recommendations, not a requirement to spawn agents. Prefer fewer agents unless parallel work clearly reduces risk or time.

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
- If a sub-agent does not return useful status within the timeout, stop waiting, inspect local state, and either close the sub-agent or continue with the controller.
- If Codex Desktop appears stuck but no command output is changing, first read the current terminal/session state or switch away and back once to refresh the UI. Treat that as a UI recovery step, not as proof the underlying task is still working.
- When sub-agents are used, the controller must keep a short list of active agents, their assigned role, and the last useful result. Do not let a completed implementation wait indefinitely for a review agent; use one bounded wait, then proceed with documented risk or close the stale agent.
- If a command fails twice with the same class of error, stop repeating it and switch to systematic debugging: identify the failing layer, form one hypothesis, and test that hypothesis with the smallest command.
- If a command appears to hang, check whether useful work has already completed before retrying. Record the last successful command and avoid rerunning broad suites unnecessarily.
- At handoff, report any interrupted or closed sub-agents, known background processes, and whether the worktree is clean.

Default timeout guidance:

- Quick file, Git, type, and unit-test checks: 30-120 seconds.
- Local service startup, packaging, or release validation: 2-10 minutes with progress updates.
- Sub-agent review or implementation: wait once with a bounded timeout, then poll or close if no status is returned.
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
