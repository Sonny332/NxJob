# NxJob Development Governance

## Purpose and Rule Priority

This document is the complete source of truth for NxJob task classification, agent gates, model requirements, execution limits, Git authorization, review, and handoff. `AGENTS.md` is only the concise Codex execution summary. Semantic governance changes must check whether `AGENTS.md` also needs synchronization.

When rules conflict, apply this priority:

1. Safety and privacy boundaries.
2. User authorization and remote-write boundaries.
3. Release quality and evidence requirements.
4. Mandatory agent gates, models, and independent review.
5. Product velocity and personal-MVP process preferences.
6. Documentation and style preferences.

No lower-priority rule may weaken a higher-priority rule. NxJob remains Windows-first, while core business logic remains platform-neutral. Phase 1 remains REST-only. User confirmation is mandatory for form filling and application submission. Bulk scraping, automatic submission, CAPTCHA bypass, and no-confirmation mass applying are prohibited.

## Documentation Size and Duplication Limits

- `AGENTS.md`: concise Chinese-first execution entry, at most approximately 250 lines or 12 KB.
- `docs/development-governance.md`: complete governance source, at most approximately 500 lines or 30 KB.
- `CLAUDE.md`: self-contained external-worker entry, at most approximately 150 lines or 10 KB.
- Do not duplicate detailed test recovery, release procedures, worker artifact schemas, or historical incidents in entry files.
- Do not create separate governance documents for agent budget, lifecycle, review loops, or interruption handling.
- Exceeding a limit requires explicit user approval and prior consolidation or deletion of existing material.

## Task Classification and Minimum Gates

Classification uses a closed allowlist. If a task does not clearly satisfy a lower gate, use the higher applicable gate.

### Controller-Direct Closed Allowlist

Controller may act directly only when there is no runtime, test, user-visible, contractual, or governance semantic change. The allowlist is limited to:

- documentation spelling, grammar, Markdown formatting, no-semantic-change wording reduction, and confirmed link/path/name synchronization;
- production-code formatting, unused-import removal, comment correction, and local-variable no-semantic rename;
- test-code formatting, comments, test-name correction, unused-import removal, and confirmed path synchronization without test-logic change;
- read-only debugging, reproduction, log reading, call-path search, and existing-check execution;
- allowed Git reads, `fetch`, local branch/worktree setup, and qualified local commit;
- existing lint, type checks, project test wrappers, short-lived local build/service checks, and cleanup of temporary artifacts created by the current task.

Any change to a condition, default, return, exception, assertion, fixture, mock, path, command argument, user-visible meaning, or product rule exits Controller-direct.

### Implementer Only

Minimum role: GPT-5.4 / Medium Implementer.

Eligible only when all applicable conditions hold:

- the change is local and behavior-preserving, or fixes a clearly reproduced single-module bug;
- no external contract or mandatory Reviewer category is affected;
- targeted automated verification is available;
- there is no privacy, submission-confirmation, migration, installer, release, high-risk path/process, or cross-subsystem impact.

Typical cases include a local behavior-preserving refactor, a clearly reproduced single-module bug with regression coverage, an ordinary documentation semantic update, a visual-only UI correction, a clearly non-semantic copy correction, a non-high-risk development-script adjustment, or an ordinary test semantic addition.

### Implementer + Independent Reviewer

Minimum roles:

- GPT-5.4 / Medium Implementer;
- independent GPT-5.6 Terra / High Reviewer, unless a Sol trigger applies.

This gate is mandatory for:

- any new user capability or UI interaction/state/form/confirmation/error/empty/loading/success behavior;
- API, schema, database field, enum, serialization, or external-contract semantics;
- privacy, logs, PromptLog, credentials, real data, or plugin-visible errors;
- install, uninstall, packaging, background startup, Windows path/process arguments;
- browser-extension permissions or manifest behavior;
- test deletion, assertion weakening, skip, xfail, or ignore changes;
- cross-module or incompletely understood fixes, shared/public functions, or shared components;
- changes not reliably covered by targeted checks;
- semantic changes to key governance, release, privacy, API, data-model, or safety documents.

The independent Reviewer must be a separate agent/thread and must not modify the reviewed implementation.

### Planner + Implementer + Independent Reviewer

Controller, Planner, and Reviewer use GPT-5.6 Sol / High. Implementer remains GPT-5.4 / Medium.

This gate is mandatory when a task:

- adds, removes, or repartitions a module, service, or runtime;
- changes responsibility or call direction across plugin, local service, API, or database;
- affects two or more independent runtime subsystems;
- performs a schema/database migration or existing-data compatibility, conversion, repair, or deletion;
- changes core object relationships, state model, or data lifecycle;
- adds a provider, platform, persistence mechanism, or data source;
- changes a core technical boundary, including Phase 1 REST-only;
- changes privacy, confirmation, submission, scraping, CAPTCHA, or automation boundaries;
- changes mandatory gates, required models, approval permissions, rule priority, or source-of-truth policy;
- has no clear single implementation approach before coding;
- is difficult to roll back or requires staged implementation.

### Formal Release

Required sequence:

1. GPT-5.4 / Medium Implementer.
2. GPT-5.4 / Medium Release Agent.
3. Independent GPT-5.6 Terra or Sol / High Reviewer.
4. Controller recommendation.
5. Explicit user authorization for remote publication.

The Release Agent records build, artifact, installation, version, and privacy evidence. It cannot approve release readiness, modify production code, create tags, push, create GitHub Releases, or upload artifacts.

## Roles, Models, and Reasoning Effort

| Role | Normal task | Architecture / major-impact task |
| --- | --- | --- |
| Controller | GPT-5.6 Terra / High | GPT-5.6 Sol / High |
| Planner / Architect | GPT-5.6 Terra / High | GPT-5.6 Sol / High |
| Reviewer / Evaluator | GPT-5.6 Terra / High | GPT-5.6 Sol / High |
| Implementer | GPT-5.4 / Medium | GPT-5.4 / Medium |
| Release Agent | GPT-5.4 / Medium | GPT-5.4 / Medium |
| Test Agent | GPT-5.4 / Medium | GPT-5.4 / Medium |
| Code Mapper | GPT-5 mini / Low | GPT-5 mini / Low |
| Docs Agent | GPT-5 mini / Low | GPT-5 mini / Low |
| Form Answer Agent | GPT-5 mini / Medium | GPT-5 mini / Medium |
| Resume Quality Agent | GPT-5.6 Terra / High | GPT-5.6 Sol / High |

Models and reasoning effort are hard requirements. An unavailable or unconfirmed required model does not satisfy a gate. Do not silently substitute a model or reduce reasoning effort. After one targeted retry, stop and report the blocker.

## Sol Upgrade Triggers

Use GPT-5.6 Sol / High for Controller, Planner, and Reviewer whenever any Planner gate trigger applies. Also upgrade for major-impact privacy, safety, migration, architecture, governance-authority, release-readiness, or difficult-rollback decisions. Resume Quality Agent upgrades to GPT-5.6 Sol / High when the same major-impact triggers apply.

## Optional Specialized Roles

- **Code Mapper:** GPT-5 mini / Low, read-only. Use only when bounded search cannot find the entry point, at least three production modules may be affected, cross-layer flow must be mapped, or the user requests mapping.
- **Test Agent:** GPT-5.4 / Medium. Use for a substantial independent test package, multi-module matrix, flaky-test investigation, complex read-only reproduction, or formal release validation.
- **Docs Agent:** GPT-5 mini / Low. Use for multi-document consistency, index restructuring, broad link checks, or a bounded documentation package.
- **External worker:** default-off auxiliary worker, used only by explicit request or when a bounded packet clearly lowers total cost.

Code Mapper, Test Agent, and Docs Agent are optional and conditional, never default gates. External workers cannot satisfy mandatory Implementer, Reviewer, or Release gates. Their output must be adopted, corrected, and verified by the required native role.

## Unified Execution-Lane Budget

A lane is any native Codex sub-agent or external worker; Controller is not a lane.

- Default active execution lane: 1.
- Hard maximum active lanes: 2.
- Project depth maximum: 1.
- Two lanes are allowed only for independent, non-overlapping work with no ordering dependency and a clear completion-time benefit.
- Native agents and external workers share the same budget.
- Exceeding the task's default agent count or hard lane limit requires explicit user approval.
- `max_threads = 2` is a ceiling, not a target.

| Task | Default maximum new agents |
| --- | ---: |
| Controller-direct | 0 |
| Implementer only | 1 |
| Implementer + Reviewer | 2 |
| Planner + Implementer + Reviewer | 3, sequential |
| Formal release | 3, sequential |
| Optional specialized role | Only on an explicit trigger |

## Agent Lifecycle, Retry, and Review Loops

- Code Mapper closes when mapping is received.
- Planner closes when design, boundaries, and acceptance criteria are received.
- Implementer remains available through Reviewer feedback and closes after final pass.
- Reviewer remains only when re-review is required; otherwise it closes after a clear decision.
- Docs, Test, and Release agents close after evidence is received and recorded.
- Unconfirmed closure is reported as `stale — closure unconfirmed` and never counts as a gate pass.

For each required role there are at most two total startup attempts: one normal attempt and one targeted retry after narrowing or correcting the task packet. If the second attempt fails, stop expansion and return control to the user. Failure never grants Controller new implementation, review, or release authority.

External workers receive the same single targeted retry only after packet, route, environment, or input materially changes. There is no automatic provider/model escalation chain.

The Implementer–Reviewer loop is limited to initial review, first fix and re-review, and second fix and re-review. If the second re-review does not pass, stop and report remaining issues.

## Interruption Checkpoint

The Interruption Checkpoint is event-triggered only. Create one when the user requests a pause, the platform reports quota/rate/session interruption, a natural stage ends before another high-cost agent, or work cannot continue because a session or agent was interrupted.

Record only current branch/worktree, last verified commit, changed uncommitted files, last completed verification, active/completed/stale agents, exact next action, and known blockers. Never predict quota or context limits. A checkpoint does not change acceptance criteria, reduce verification, replace review, create a premature commit, or close a useful agent.

## Worktree, PR, Git, and Command Boundaries

| Worktree is mandatory | Worktree is not mandatory by itself |
| --- | --- |
| Sol-level architecture/major-impact work; migration or data conversion; formal release candidate; parallel Implementers; mutually exclusive experiments; two or more independent runtime subsystems; unsafe rollback; unsafe-to-share dirty workspace; explicit user request | Controller-direct work; read-only investigation; local single-module bug; document cleanup; local visual fix; bounded test adjustment; merely using Implementer or Reviewer |

| PR preparation is mandatory | PR is not automatic |
| --- | --- |
| Architecture/major impact; migration; privacy/safety/confirmation/automation boundary; formal release candidate; two or more runtime subsystems; parallel integration; core API or plugin/service contract; high rollback risk; remote review-history requirement; explicit user request | Local work that does not meet a PR trigger |

| Autonomous Git operations | Require explicit user approval |
| --- | --- |
| Status, diff, log, branch inspection; fetch and read-only remote comparison; local branch and qualified worktree creation; qualified local commit | Pull, merge, rebase; destructive reset or forced checkout; deletion of unmerged branches/worktrees; push; PR create/update; tag; GitHub Release; artifact upload |

Before worktree creation, fetch and compare with the remote. Do not automatically pull. Local commit is allowed only after scoped work and mandatory gates are complete, checks pass, no out-of-scope/sensitive/user changes are mixed in, and the commit is one coherent goal.

| Autonomous command effects | Require explicit user approval |
| --- | --- |
| Read/search; existing lint/type/project test wrappers; short-lived local build/service checks; task-created temporary artifacts; local packaging tests; read-only GitHub queries | Dependency or unrelated lockfile changes; user/system environment or global-tool changes; real-data migration/deletion; non-task directory deletion; network/API writes; unapproved sandbox-external commands; Windows service/registry/scheduled-task/startup changes; formal install/update/uninstall; real-private-data testing |

Permanently prohibited: administrator/UAC/system execution; broad ACL grants; automatic job submission; CAPTCHA bypass; no-confirmation bulk scraping or applying; silent upload of resumes, databases, PromptLog, or credentials; automatic push, merge, tag, Release, or artifact upload.

Windows path values must be quoted and passed through `-LiteralPath`, argument arrays, or structured parameters rather than manually joined shell strings. Paths containing spaces are a required packaging/startup test case.

## Reviewer Verification

Reviewer must independently inspect the actual diff, acceptance criteria, and Implementer commands/results; check for weakened assertions, changed expected values, skip/xfail abuse, and missing edge cases; and run at least one check targeted at the central risk. Reviewer does not automatically repeat the full suite.

Critical tests must be rerun for API/schema/data, privacy/safety, install/path/process, migration, cross-module features, formal release, incomplete evidence, insufficient targeted coverage, broad regression risk, specialized-document requirements, or explicit user request.

Reviewer reports evidence reviewed, independent checks run, checks intentionally not repeated, residual risk, and one decision: `PASS`, `CHANGES_REQUIRED`, or `BLOCKED`.

## Phase-Specific Skill Gates

### Superpowers Feature and Bug Workflows

Superpowers is a phase-specific workflow gate, not a new agent role. It never replaces NxJob Planner, Implementer, Reviewer, Release, privacy, authorization, or user-confirmation requirements.

Formal feature-development triggers include:

- adding a new user-facing feature;
- materially changing existing behavior;
- multi-step or cross-module implementation;
- architecture, schema, state-model, data-flow, privacy, or compatibility changes;
- requirements with multiple reasonable implementation approaches; or
- work explicitly classified as formal feature development.

Default feature workflow:

`brainstorming → user-approved design → writing-plans → executing-plans or subagent-driven-development → verification-before-completion → required NxJob Reviewer Gate`

Bug fixes use the applicable debugging workflow instead:

`systematic-debugging → root-cause confirmation → test-driven-development where applicable → implementation → verification-before-completion → Reviewer Gate when required by the task matrix`

The complete feature workflow is not required for Controller-direct mechanical changes, read-only investigation, spelling/formatting/non-semantic documentation changes, a narrowly scoped fix already covered by an approved implementation plan, or a local correction explicitly requested by a Reviewer. These are workflow exemptions only and do not weaken any mandatory gate.

### Ponytail Gate Conditions, Prohibitions, and Exclusions

Ponytail is advisory, read-only, and default-off. Invoke it explicitly as `@ponytail-review`.

Ponytail must not:

- modify code directly;
- satisfy the mandatory NxJob Reviewer Gate;
- approve merge or release;
- override architecture, privacy, security, compatibility, schema, state-model, user-confirmation, or release rules; or
- automatically trigger implementation of its recommendations.

Ponytail may run only after all of the following are true:

- a feature was added or materially changed;
- development occurred on a feature branch or isolated worktree;
- automated verification passed;
- the mandatory NxJob Reviewer passed;
- the user completed manual testing and confirmed the feature behavior; and
- the branch has not yet been merged or formally released.

Controller-direct work, pure documentation changes, read-only investigation, ordinary local bug fixes without a feature branch, Reviewer follow-up fixes, and release operations themselves do not trigger the Ponytail gate.

### Ponytail Baseline and Scope

The default Ponytail scope is the complete feature-branch or worktree diff relative to the exact recorded baseline commit. When a qualifying feature branch or worktree is created, record in the task handoff or Interruption Checkpoint:

- `Base branch: <branch>`
- `Baseline commit: <full commit SHA>`
- `Feature branch: <branch>`
- `Baseline status: recorded`

Run Ponytail against the full branch history:

`git diff <baseline-commit>...HEAD`

Do not limit Ponytail to staged, unstaged, or otherwise uncommitted working-tree changes. Later updates to the base branch do not redefine the recorded baseline.

If the original baseline record is missing:

1. compute a candidate with `git merge-base`;
2. mark it as `inferred baseline`;
3. request user confirmation before running Ponytail; and
4. do not silently assume the current local or remote main branch was the original baseline.

### Ponytail Finding Intake and Disposition

Every Ponytail finding first enters `superpowers:receiving-code-review`, then is reclassified under the NxJob task matrix.

Disposition values:

- `ACCEPT_SAFE`: clearly redundant and removable without behavior change;
- `ACCEPT_WITH_REVIEW`: valuable simplification that affects shared or important code;
- `RECLASSIFY`: actually affects architecture, API, schema, privacy, compatibility, state, or another higher-risk area;
- `REJECT_GOVERNANCE`: apparently redundant code is required by governance, privacy, safety, compatibility, or user-control rules;
- `REJECT_LOW_VALUE`: possible reduction exists, but value is lower than regression or maintenance risk; and
- `USER_DECISION`: the suggestion is a product or architecture trade-off requiring user judgment.

Ponytail output is evidence, not an instruction to delete code.

### Post-Finding Flows and Review Limits

For clearly behavior-preserving cleanup:

`receiving-code-review → original Implementer applies accepted changes → targeted verification → verification-before-completion → independent Reviewer re-review`

A full new brainstorming and planning cycle is not required for obvious dead code, unused imports, temporary debugging code, strictly equivalent standard-library replacements, or fully duplicated local logic.

For findings that may affect behavior, shared boundaries, fallbacks, error handling, or compatibility:

`receiving-code-review → impact investigation or systematic-debugging → reclassification under the NxJob task matrix → required Implementer and Reviewer flow → targeted user retesting when applicable`

For architecture, schema, privacy, state-model, compatibility, user-confirmation, or major framework changes, treat the proposal as a new formal task:

`brainstorming → user-approved design → writing-plans → controlled implementation → verification-before-completion → required Terra or Sol Reviewer Gate`

Each qualifying feature branch receives one full Ponytail review by default. Do not create an automatic `Ponytail → cleanup → Ponytail → cleanup` loop.

A second full Ponytail review is allowed only when:

- the cleanup itself caused a substantial structural change;
- the first review was intentionally processed in stages and the remaining diff materially changed;
- the independent Reviewer identifies evidence that cleanup introduced new duplication or temporary compatibility code; or
- the user explicitly requests another review.

Correctness after accepted cleanup is established through Superpowers, automated verification, and the independent NxJob Reviewer, not by repeated Ponytail invocation.

### Verification, Retesting, and Final Handoff Evidence

After accepted Ponytail changes:

- run targeted automated verification;
- use `verification-before-completion`;
- obtain an independent Reviewer result; and
- do not weaken, delete, skip, or rewrite tests merely to accommodate cleanup.

Targeted user retesting is required when cleanup touches user-visible execution paths, UI behavior or state, plugin or local-service interaction, resume generation, form-answer behavior, application tracking, or startup, installer, packaging, or path behavior.

Repeat full user acceptance when cleanup changes product behavior, core state semantics, privacy boundaries, compatibility, or user-confirmation behavior.

Do not commit the complete raw Ponytail report by default. Record concise handoff evidence only:

- `Ponytail review scope`
- `Base branch`
- `Baseline commit`
- `Reviewed HEAD`
- `Review status`
- finding counts or summaries for `ACCEPT_SAFE`, `ACCEPT_WITH_REVIEW`, `RECLASSIFY`, `REJECT_GOVERNANCE`, `REJECT_LOW_VALUE`, and `USER_DECISION`
- accepted changes
- rejected findings and reasons
- verification after cleanup
- independent Reviewer result
- user retesting status

Keep full raw Ponytail output only as a temporary artifact when it has clear audit value.

## Documentation Routing and Sources of Truth

Ordinary tasks read `AGENTS.md + 1` directly relevant specialized document. High-risk or cross-domain tasks read `AGENTS.md`, this governance document, and 1–2 directly relevant specialized documents. Do not scan all documents by default.

| Domain | Source of truth |
| --- | --- |
| Agent roles, models, gates | `docs/development-governance.md` |
| Codex execution summary | `AGENTS.md` |
| External-worker contract | `CLAUDE.md` plus approved task packet |
| Safety, privacy, confirmation | `docs/privacy-boundary.md` plus governance |
| Current MVP scope | Current sections of `docs/mvp-scope.md` |
| Long-term product direction | `docs/product-blueprint.md` |
| Technical boundary | `docs/tech-stack.md` |
| API | `docs/api-schema.md` plus current shared schema/code |
| Data model | `docs/data-model.md` plus current models/migrations |
| UI | `docs/design.md` |
| Release | `docs/release-checklist.md`, `docs/versioning.md`, `docs/release-hardening.md` |
| User installation | `README.md` plus `docs/install-windows.md` |
| Actual repository structure | Actual file tree first; `docs/project-structure.md` as description/target |

Historical, Future, Post-MVP, and Phase 2/3 text is not a current implementation requirement. Code does not automatically override specification, and specification does not prove implementation; report mismatches.

Windows pytest uses `scripts/run_pytest.ps1` or `scripts/test-local-service.ps1`; detailed recovery belongs in the specialized test rules. On known ACL failures, stop repeated attempts and request only the exact wrapper sandbox exception while remaining non-admin. Never use elevation or broaden global ACLs.

## Public Repository and Release Governance

NxJob is already public. Every stable release receives incremental privacy checks of the current tree, release diff, artifacts, Actions output, and user-visible errors/logs. A deep history/security audit is required only when triggered by privacy-boundary, workflow, packaging, secret, telemetry/upload, history-rewrite, repository-security-setting changes, a suspected leak, or explicit user request.

A stable release requires all applicable automated and manual checks. Missing or incomplete evidence permits only a development build or explicitly marked pre-release. Every `N/A` entry requires a reason.

The formal version source is the explicit `scripts/package/build-release.ps1 -Version <version>` input. Version metadata, artifact names/content, manifest, release-test record, release notes folder, tag, and GitHub Release must match. Tags and remote publication happen only after build and validation pass and explicit user authorization.

## Final Handoff

Every final handoff includes these core fields:

- status;
- goal and scope completed;
- changed files;
- verification commands actually run and results;
- unverified or skipped checks with reasons;
- risks and blockers;
- Git branch/worktree, commit hash if any, and pushed/unpushed state;
- exact next recommended action.

Conditional fields include agent nickname, assigned role, exact model, reasoning effort, state, whether output was used, retries, stale closures, Reviewer decision, release evidence, user authorization status, and interruption checkpoint. Unknown required model metadata is reported as `unknown, not acceptable for required gate`.

External-worker implementation/failure reports remain separate artifacts and never replace the Controller final handoff.

## Existing Rule Handling

Merge overlapping rules instead of duplicating them. Keep the clearest specific wording and preserve stricter safety, privacy, authorization, and release requirements. Remove outdated blanket sub-agent requirements, automatic capability ladders, failure-based Controller bypasses, and detailed procedures that belong in specialized documents. When a conflict is genuinely unclear, report it for user decision rather than silently deleting a key boundary.
