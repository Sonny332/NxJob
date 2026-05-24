# Agent Task Artifacts

`.agent_tasks/` is a workspace-local task artifact area. The repository boundary is intentionally narrow:

- Commit: `README.md`, `templates/*.md`, `templates/*.json`
- Do not commit: task runtime folders, packet instances, prompts, heartbeats, status snapshots, logs, captured output, or human notes tied to a specific run

## Artifact Roles

- `task packet`: controller-authored work order. It defines the bounded objective, allowed paths, stop conditions, and approved checks before a worker starts.
- `worker heartbeat`: optional in-progress snapshot for longer tasks. Use it only when the controller needs off-chat progress visibility.
- `worker status`: required machine-readable finish-or-stop artifact. Every packet should end with one final status snapshot.
- `failure report`: concise stop report for `blocked`, `failed`, or otherwise incomplete exits. It records the smallest reliable evidence and the next controller action.
- `implementation report`: concise completion handoff for a finished packet. It records changed files, verification, blockers, and a safe resume point.
- `human observation`: optional manual note for evidence that cannot be captured reliably by the worker alone, such as a UI observation or human judgment call.

## Template Files

- `templates/task_packet.template.md`
- `templates/failure_report.template.md`
- `templates/implementation_report.template.md`
- `templates/human_observation.template.md`
- `templates/worker_heartbeat.template.json`
- `templates/worker_status.template.json`

Templates must stay short, reusable, and free of real task data, secrets, cookies, API keys, browser profiles, or production records.

## Runtime Boundary

Runtime task folders may contain:

- instantiated packets
- prompt files
- heartbeat and status snapshots
- failure or implementation reports for one run
- test output, logs, and other temporary evidence

These runtime artifacts are intentionally local-only. Keep them inspectable, compact, and safe, but do not promote them into committed repository history.

## Suggested Flow

1. Controller approves a bounded task packet.
2. Worker executes only within the approved scope.
3. Worker writes a heartbeat only when bounded progress visibility is useful.
4. Worker always writes a final `worker status`.
5. Worker writes either a `failure report` or an `implementation report`.
6. Add `human observation` only when manual evidence materially affects controller or reviewer judgment.
