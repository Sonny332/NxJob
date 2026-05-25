# Harness Lessons

Use this file to capture repeated workflow failures and the lesson that should change future controller or worker behavior.

## Entry Format

Add a short section per repeated lesson using this template:

```md
## <YYYY-MM-DD> <short-title>

- failure_class:
- trigger:
- symptoms:
- root_cause_hypothesis:
- mitigation:
- prevention_update:
- artifact_examples:
- status:
- resume_impact:
```

Guidance:

- `failure_class`: use one class from `docs/routing-rules.md`.
- `trigger`: what action or packet exposed the problem.
- `symptoms`: the smallest evidence set that reliably identifies the issue.
- `root_cause_hypothesis`: current best explanation, even if not final.
- `mitigation`: what changed to restore progress.
- `prevention_update`: what should be updated in wrapper, docs, templates, or governance.
- `artifact_examples`: file paths or packet ids, never secrets or full logs.
- `status`: `candidate`, `confirmed`, or `superseded`.
- `resume_impact`: how the controller should alter the next `/goal` resume or next packet.

Use this file for repeated classes and changed workflow expectations, not for every retry. One-off failures belong in the packet's `failure_report.md`.

## Repeated Failure Rule

When the same failure class repeats, prefer appending a new lesson entry or updating the latest relevant entry instead of scattering notes across chat logs.

If the same class repeats enough to change workflow expectations, also update:

- `docs/development-governance.md` when governance behavior must change;
- `docs/routing-rules.md` when escalation behavior must change;
- `.agent_tasks/templates/*` when the artifact contract must change.

## 2026-05-24 oversized-worker-packet-timeout

- failure_class: packet_definition
- trigger: assigning one worker a broad stabilization packet covering `.agent_tasks`, `.claude`, docs, scripts, and validation checks.
- symptoms: worker remained `running` past bounded waits and produced no usable diff or handoff artifact.
- root_cause_hypothesis: the task packet was too broad for reliable bounded worker execution and encouraged excessive repo reading before action.
- mitigation: close stale worker, split into smaller packets by write scope, and retry with a narrower implementer task.
- prevention_update: future worker packets should own a small file group or a single responsibility; broad governance passes should be decomposed into `.agent_tasks`, `.claude/docs`, `scripts`, and review-only packets.
- artifact_examples: sub-agent timeout during worker orchestration stabilization; no secrets or full logs retained.
- status: confirmed

## 2026-05-24 windows-python314-pytest-temp-acl

- failure_class: environment_runtime
- trigger: sub-agents and controller runs calling raw `python -m pytest` on Windows.
- symptoms: `PermissionError: [WinError 5] Access is denied` while creating or cleaning pytest temp directories; SQLite tests can also fail with `sqlite3.OperationalError: disk I/O error` when the database is created under those temp paths.
- root_cause_hypothesis: Python 3.14 / pytest creates temporary directories through `os.mkdir(..., 0o700)`, producing unusable ACLs on this Windows host. Separately, SQLite databases created under the repository's D-drive ACL can fail with disk I/O errors even when text writes succeed.
- mitigation: run Python tests through `scripts/run_pytest.ps1` or `scripts/test-local-service.ps1`; the wrapper applies a process-local mkdir mode patch before importing pytest and keeps runtime artifacts under the Windows temp folder.
- prevention_update: task packets, worker prompts, and release checks should reference the wrapper instead of raw `python -m pytest`.
- artifact_examples: pytest failures from 0.6.0 form-answer validation and follow-up worker runs; no secrets or full logs retained.
- status: confirmed
- resume_impact: future `/goal` resumes should state that Python test commands must use the NxJob pytest wrapper on Windows.
