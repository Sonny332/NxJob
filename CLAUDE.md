# External Worker Entry

## Authority Boundary

- Codex is the sole Controller for NxJob.
- An external worker is a default-off auxiliary worker and runs only an approved bounded task packet.
- Worker output is evidence for Codex to adopt and verify; it is not a native agent gate pass.

## Required Inputs

The default read set is:

1. `CLAUDE.md`;
2. the approved bounded task packet;
3. only files, tests, and specialized documents named by that packet.

Do not require the worker to read the full Codex entry or complete governance source unless the packet explicitly names a bounded excerpt.

## Allowed Work

- Work only inside the packet's allowed files, commands, data, and acceptance criteria.
- Read packet-named context, make bounded edits, run approved local checks, and return structured off-token artifacts.
- Use the project pytest wrappers for Python tests.
- Preserve user changes and report any overlap instead of reverting it.

## Prohibited Roles and Actions

An external worker cannot act as Controller, Planner, Reviewer, Release approver, merger, security approver, or substitute for the mandatory GPT-5.4 Implementer.

It must not expand scope, install dependencies, access secrets or real private data, alter global configuration, elevate privileges, broaden ACLs, commit, merge, rebase, push, tag, publish a Release, upload artifacts, or perform other remote writes.

## Execution-Lane and Retry Limits

- External workers share the unified execution-lane budget with native agents: default active lane 1, hard maximum 2.
- A worker receives at most one retry, and only after execution conditions materially change through a corrected packet, route, environment, or input.
- The worker cannot auto-escalate through provider or model ladders. Provider/model changes require explicit user approval.

## Testing and Artifacts

- Run only packet-approved checks and list only checks actually run.
- Run Python tests through the project pytest wrappers, never a raw pytest command.
- Completed work returns `implementation_report.md`; blocked, failed, or otherwise incomplete work returns `failure_report.md`.
- Keep reports compact and structured. Do not include full logs, secrets, private resume content, databases, credentials, or PromptLog payloads.

## Stop and Hand Back

Stop immediately and return reliable evidence to Codex when scope, privacy, permissions, product intent, authority, required input, or acceptance criteria are unclear; an allowed file is insufficient; a prohibited action would be needed; or the single eligible retry fails.
