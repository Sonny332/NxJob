# External-Worker Development Contract

This document defines only NxJob's external-worker execution contract. `CLAUDE.md` defines worker authority; `docs/development-governance.md` defines native agent gates.

## Activation and Authority

- Codex is the sole Controller.
- External workers are default-off optional auxiliaries, not the default workflow.
- A worker runs only when the Controller approves a bounded task packet.
- A worker cannot satisfy mandatory GPT-5.4 Implementer, independent Reviewer, or Release Agent gates.
- Worker output must be adopted and verified by the required native role before it can support a gate.

## Responsibilities

The Controller:

- approves objective, allowed files, checks, inputs, stop conditions, and artifact paths;
- decides whether an auxiliary worker has a clear completion benefit;
- consumes structured artifacts and decides the next workflow step;
- preserves safety, privacy, authorization, and native gate requirements;
- closes the worker after its artifacts are consumed.

The worker:

- performs only the approved packet;
- edits only allowed files and runs only approved checks;
- reports status through structured off-token artifacts;
- stops when scope, authority, privacy, permission, product intent, or required input is unclear;
- never claims Controller, Planner, Implementer, Reviewer, Release, security, merge, or publication authority.

## Approved Packet Lifecycle

1. Controller approves one bounded packet.
2. Wrapper validates packet and artifact paths.
3. Worker executes inside the allowed scope.
4. Controller observes bounded heartbeat/status signals as needed.
5. Worker reaches `completed`, `stalled`, `blocked`, or `failed`.
6. `completed` produces only `implementation_report.md`; every other terminal state produces only `failure_report.md`.
7. Controller consumes the report, closes the worker, and routes any remaining work through the normal native gate.

Do not routinely decompose broad governance work into several external-worker packets. Broad governance belongs in the approved native Planner/Implementer/Reviewer workflow. Use an external worker only for a genuinely bounded auxiliary packet.

## Unified Execution-Lane Budget

External workers and native Codex agents share the unified execution-lane budget:

- default active lane: 1;
- hard maximum active lanes: 2;
- two lanes only for independent, non-overlapping work with no ordering dependency and clear completion benefit;
- the Controller is not a lane.

## Structured Signals and Artifacts

Use these off-token signals:

- `worker_heartbeat.json`: optional in-progress heartbeat;
- `worker_status.json`: required machine-readable current or terminal state;
- `implementation_report.md`: the only report for `completed`;
- `failure_report.md`: the only report for `stalled`, `blocked`, or `failed`;
- `human_observation.md`: optional bounded manual evidence;
- `test_output.txt`: approved check output when needed.

Full `worker_log.ndjson` is diagnostic evidence, not a polling surface. Never copy secrets, private resume content, credentials, production data, or PromptLog payloads into artifacts.

Python tests use `scripts/run_pytest.ps1` or `scripts/test-local-service.ps1`, never raw `python -m pytest`.

## Worker States

| State | Meaning | Controller action |
| --- | --- | --- |
| `busy` | Worker is making expected progress in packet scope. | Wait only within the bounded observation window. |
| `stalled` | Worker is alive but no longer making useful progress. | Stop the run and consume `failure_report.md`. |
| `blocked` | Worker needs missing input, permission, or a human decision. | Consume `failure_report.md` and resolve outside the worker. |
| `failed` | Execution or environment ended the worker path unsuccessfully. | Consume `failure_report.md` and classify the failure. |
| `completed` | Worker completed the approved packet. | Consume `implementation_report.md`; do not infer a native gate pass. |

## Reuse, Isolation, and Retry

Reuse a worker context only when the next action remains inside the same approved packet frame, files, assumptions, privacy boundary, and objective. Otherwise start an isolated run if an auxiliary worker is still justified.

One retry is allowed only after the packet, route, environment, or input materially changes. If that retry fails:

- stop the external-worker path;
- hand reliable artifacts to the Controller;
- do not switch provider/model automatically;
- enter the normal GPT-5.4 Implementer gate as a separate workflow if implementation is still required.

Worker completion cannot satisfy mandatory native gates, and retry failure never grants the Controller or worker additional authority.
