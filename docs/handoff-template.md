# Implementation Report Template

Use this template for controller-facing completed-work handoff. It is designed to support `/goal` resume without replaying full logs.

## Required Sections

```md
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

<2-6 short bullets with the most important outcomes>

## Evidence

- heartbeat_artifact:
- status_artifact:
- human_observation_artifact:
- diff_or_validation_artifact:

## /goal Resume Seed

Use this section to give the controller a compact resume point:

- current_goal:
- completed_work:
- remaining_work:
- decisions_already_made:
- open_questions:
- safe_resume_point:
- resume_command_hint:
```

## Usage Notes

- `failure_class` may be `none` when `final_state` is `completed`.
- `changed_files` should stay scoped to the approved packet.
- `verification` should list only checks actually run.
- `safe_resume_point` should name the next packet or decision boundary, not a vague instruction such as "continue working".
- `resume_command_hint` should be a short `/goal`-friendly phrase, not a long narrative.
- Prefer artifact file references over pasted logs.

## Related Artifacts

This report is for completed implementation work. When the worker stops without completion, use `failure_report.md` instead and keep `/goal` resume notes inside that failure path only if the controller still needs them.
