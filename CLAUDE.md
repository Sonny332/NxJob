# Claude Worker Entry

本文件只做 Claude CLI worker 入口索引。主规则仍以 [`AGENTS.md`](AGENTS.md) 和 [`docs/development-governance.md`](docs/development-governance.md) 为准。

## Controller Boundary

- Codex is the controller for NxJob.
- Claude CLI workers are bounded execution lanes, not workflow authorities.
- Workers do not act as reviewer, releaser, merger, security approver, or architecture authority.

## Read In Order

1. [`AGENTS.md`](AGENTS.md)
2. [`docs/development-governance.md`](docs/development-governance.md)
3. [`docs/multi-agent-development.md`](docs/multi-agent-development.md)
4. [`docs/routing-rules.md`](docs/routing-rules.md)
5. [`docs/hooks-playbook.md`](docs/hooks-playbook.md)
6. [`docs/handoff-template.md`](docs/handoff-template.md)
7. [`docs/harness-lessons.md`](docs/harness-lessons.md)
8. [`scripts/run_claude_worker.ps1`](scripts/run_claude_worker.ps1)
9. [`scripts/run_pytest.ps1`](scripts/run_pytest.ps1)
10. [`scripts/test-local-service.ps1`](scripts/test-local-service.ps1)
11. [`scripts/check_hooks.ps1`](scripts/check_hooks.ps1)

## Worker Reminder

- Execute only approved task packets.
- Stay inside approved files and approved checks.
- Run Python tests through `scripts/run_pytest.ps1` or `scripts/test-local-service.ps1`, not raw `python -m pytest`.
- Return compact off-token artifacts for controller handoff.
- Stop and hand back control when packet scope, routing, privacy, or authority is unclear.
