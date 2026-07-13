# Task Packet

- packet_id:
- task_title:
- worker_role: Auxiliary Worker
- requested_model:
- reasoning_effort:
- owner_controller:
- created_at:

## Objective

State the bounded auxiliary outcome in 1-3 sentences.

## Allowed Scope

- allowed_paths:
- forbidden_paths:
- in_scope_changes:
- out_of_scope_changes:

## Inputs

- required_files:
- supporting_docs:
- existing_artifacts:

## Stop Conditions

- Stop when the bounded implementation is complete.
- Stop when a required file, route, dependency, or decision is missing.
- Stop when the task would require architecture, release, security, merge, or review approval authority.

## Approved Checks

- command: powershell -NoProfile -ExecutionPolicy Bypass -File scripts\test-local-service.ps1
- command:

## Output Contract

- required_status_artifact:
- completed_report: implementation_report.md
- non_completed_report: failure_report.md
- optional_artifacts:

## Notes

- Do not place secrets, API keys, cookies, browser profiles, or real user data in this packet.
- Reference sensitive material by approved local path only when the worker is explicitly allowed to read it.
- This packet is default-off and cannot satisfy a mandatory GPT-5.4 Implementer, Reviewer, or Release gate.
- Permit at most one retry after packet, route, environment, or input materially changes; never auto-switch provider/model.
