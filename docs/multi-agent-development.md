# Multi-Agent Development

This document defines only the execution contract for NxJob's Claude CLI + DeepSeek worker path.

Workflow authority stays in [`AGENTS.md`](../AGENTS.md) and [`docs/development-governance.md`](development-governance.md). This file does not replace reviewer gates, release rules, or agent-role requirements.

## Scope

- Codex remains the controller.
- Claude Code CLI workers execute only approved task packets.
- DeepSeek workers are bounded implementation workers, not architecture, release, security, merge, or review agents.
- Review, merge, push, release, and production actions remain outside worker authority.

## Roles

### Controller

The controller:

- defines scope, acceptance, and stop conditions;
- prepares or approves task packets;
- chooses whether to reuse a worker context or start an isolated run;
- consumes structured worker artifacts and decides the next action;
- keeps safety, privacy, and required reviewer gates intact;
- applies human override when worker execution is no longer the right lane.

### Worker

The worker:

- executes only the assigned packet;
- keeps status observable through off-token artifacts first;
- stops when the packet is complete, blocked, or no longer safe;
- returns a compact handoff instead of streaming full logs.

## Lifecycle

1. Packet approval: controller approves a bounded task packet.
2. Launch: wrapper starts a worker with explicit packet scope and artifact paths.
3. Execution: worker edits only allowed files and writes structured status.
4. Observation: controller reads heartbeat, status, and human observation artifacts as needed.
5. Resolution: worker ends in `completed`, `blocked`, `failed`, or an explicit controller stop.
6. Reporting: worker emits an implementation report for completed implementation work, or a failure report for non-completed outcomes.
7. Handoff: controller resumes from the report artifacts without replaying the session.

## Packet Size

Keep worker packets small enough to finish inside one bounded run.

- Prefer one responsibility and a narrow write scope per packet.
- Split broad governance work into separate `.agent_tasks`, `.claude/docs`, `scripts`, and review-only packets.
- If a worker times out without a usable handoff, close it, classify the failure, and retry with a smaller packet instead of repeating the same broad prompt.
- A smaller packet is preferred over upgrading the model when the failure class is packet size, ambiguity, or orchestration overhead.

## Observable Signals

Observability should be off-token first. Prefer:

- `worker_status.json`;
- `worker_heartbeat.json`;
- `implementation_report.md` or `failure_report.md`;
- latest stream event time;
- `git diff` growth or summary;
- `test_output.txt` growth;
- `blocker_kind`;
- `failure_class`.

These are the default signals the controller reads. Full `worker_log.ndjson` is a diagnostic artifact, not a polling surface.

Python tests should run through `scripts/run_pytest.ps1` or
`scripts/test-local-service.ps1`. Raw `python -m pytest` is not a reliable
worker command on the current Windows Python 3.14 host because pytest temp
directories can be created with unusable ACLs. The wrapper also keeps SQLite
test databases out of the repository tree, whose D-drive ACL can cause
`sqlite3.OperationalError: disk I/O error`.

Avoid:

- heavyweight dashboards;
- full-log tailing by Codex;
- conversational polling when a structured artifact can answer the question.

## Worker States

Workers should report one of these states:

| State | Meaning | Expected controller action |
| --- | --- | --- |
| `busy` | Worker is making expected progress inside packet scope. | Wait within bounded time, then inspect heartbeat again. |
| `stalled` | Worker is alive but not making useful progress because context, tooling, or ambiguity is limiting forward motion. | Inspect status and choose reuse, redirect, or escalation. |
| `blocked` | Worker cannot continue without external input, approval, or a missing dependency. | Provide missing decision or escalate by failure class. |
| `failed` | Worker ended unsuccessfully because execution or environment conditions broke the task path. | Inspect failure class and use escalation ladder. |
| `completed` | Worker finished the packet and returned a handoff. | Review artifacts and decide next packet or review gate. |

## Cache-Aware Reuse And Isolation

Reuse an existing worker only when all of the following are true:

- the next packet stays in the same problem frame;
- the worker's current context is still aligned with the files being changed;
- no prior failure suggests contaminated assumptions;
- isolation is not needed for privacy or risk reasons.

Start an isolated worker when any of the following apply:

- new packet, new subsystem, or new failure class;
- prior worker is `stalled`, `blocked`, or `failed` for context-sensitive reasons;
- manual review found drift between task packet and actual edits;
- the controller needs a clean handoff for /goal resume.

## Human Override

Human override wins over worker momentum. The controller or user may stop or redirect a worker when:

- packet scope is wrong;
- safety or privacy boundaries are at risk;
- the worker is producing noisy logs instead of structured evidence;
- a failure class needs a different execution path;
- the user wants direct controller handling for the next step.

When override happens, record:

- why the worker was interrupted;
- what artifacts are reliable;
- whether the next action should reuse or isolate context.

## Artifact Responsibilities

Use the artifact set consistently across wrapper, docs, and controller handoff:

- `task_packet.md`: controller-owned bounded scope, allowed files, approved checks, and stop conditions.
- `worker_heartbeat.json`: optional in-progress signal for bounded waiting.
- `worker_status.json`: required machine-readable finish-or-stop state.
- `failure_report.md`: required when the worker does not finish in `completed`.
- `implementation_report.md`: required when the worker completes implementation work.
- `human_observation.md`: optional manual evidence note when environment or UI observation matters.
