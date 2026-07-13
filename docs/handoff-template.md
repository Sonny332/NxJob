# External-Worker Handoff Template

This is an external-worker artifact, not the Controller's final handoff.

```markdown
# Implementation Report

- packet_id:
- worker_role:
- worker_model:
- reasoning_effort:
- final_state:
- failure_class:
- allowed_scope:
- changed_files:
- verification:
- blockers:
- next_recommended_action:

## Summary

## Evidence

## Resume Seed
```

## Rules

- `completed` work uses only `implementation_report.md`.
- `stalled`, `blocked`, `failed`, or otherwise incomplete work uses only `failure_report.md` with the same core fields.
- `verification` lists only checks actually run and their actual results.
- `changed_files` stays inside the approved packet.
- `Resume Seed` names the exact safe resume point, next decision, or next native workflow; do not write only "continue".
- Reference bounded artifacts instead of copying full logs.
- Never include secrets, private resume content, credentials, production data, or PromptLog payloads.
- Worker completion does not satisfy the mandatory GPT-5.4 Implementer, independent Reviewer, or Release gate.
