# Routing Rules

This document explains how the controller should route Claude Code CLI + DeepSeek worker execution and escalation.

## Core Policy

- Codex remains the controller.
- Claude Code CLI is the worker launcher.
- DeepSeek workers execute only approved task packets.
- Escalation is driven by `failure_class`, not by raw retry count.
- Retry count is only a symptom tracker. It must not become the routing decision by itself.

## Model Strategy

Flash and Pro are strategy labels, not hardcoded identifiers.

- Use a configurable provider alias and model id mapping.
- Do not hardcode `[1m]` or any provider-specific suffix into policy text.
- Keep packet templates and handoff artifacts provider-neutral where possible.

Recommended intent:

- `flash`: lower-cost, fast bounded execution.
- `pro`: higher-depth execution for harder packets, reviews, or failure investigation.

The wrapper or launcher should resolve the final provider alias and model id at run time.

## Failure Classes

Each unsuccessful path should map to a failure class before escalation:

| failure_class | Meaning | Typical examples |
| --- | --- | --- |
| `packet_definition` | The task packet is ambiguous, oversized, or internally inconsistent. | unclear scope, missing stop condition, conflicting allowed files |
| `routing_configuration` | Model alias, provider route, or launcher configuration is invalid or unavailable. | unresolved alias, bad model id, provider mismatch |
| `gateway_protocol` | The local proxy or provider protocol is incompatible with the requested client shape. | Responses vs Chat Completions mismatch, cc-switch route shape mismatch |
| `authentication` | Credentials or account access are missing, expired, or denied. | 401, 403, missing provider login |
| `dependency_runtime` | A local binary, package, or runtime prerequisite is missing or broken. | missing `claude`, missing PowerShell capability, dependency import failure |
| `permissions_boundary` | The worker cannot proceed because access is intentionally restricted. | secret-gated file, denied path, blocked tool |
| `environment_runtime` | Local environment prevents execution. | missing binary, broken wrapper dependency, file lock |
| `artifact_contract` | Required heartbeat, status, or handoff artifact is malformed or missing. | invalid JSON, missing handoff section |
| `policy_safety` | The request or packet would violate safety or repository rules. | auto-submit attempt, push/release attempt, production data access |
| `human_input` | A human decision or observation is required before safe continuation. | approval gate, ambiguous product decision, manual test evidence |
| `waiting_input` | The worker is paused for permission, elicitation, or a missing parameter. | permission prompt, missing model alias choice, missing manual evidence |
| `capability_context_debug` | The model appears unable to reason across the approved packet, context, or debugging path. | repeated wrong integration assumptions, fixes that break adjacent behavior, failure to use provided evidence |
| `unknown` | The failure does not yet fit a stable class. | first-seen symptom with no clear layer |

## Escalation Ladder

Escalate by failure class:

1. Classify the failure.
2. Capture the smallest reliable evidence off-token.
3. Choose the narrowest mitigation for that class.
4. Re-run only if the mitigation changed the execution conditions.
5. If the class repeats, add or refine the lesson in `docs/harness-lessons.md`.

What does not count as escalation progress:

- rerunning the same packet without changing the failure class;
- upgrading the model before packet, route, or environment changes;
- switching from one retry number to the next without a new mitigation;
- treating "third try" as a policy by itself.

Class-specific guidance:

- `packet_definition`: shrink or rewrite the packet before any rerun.
- `routing_configuration`: inspect alias and model resolution; do not burn retries on the same unresolved route.
- `gateway_protocol`: fix proxy, adapter, or client protocol before rerun.
- `authentication`: repair credentials outside the task packet; do not escalate the model.
- `dependency_runtime`: install or repair the local prerequisite; do not escalate the model.
- `permissions_boundary`: stop and ask the controller whether the boundary is intentional or the packet is wrong.
- `environment_runtime`: repair the local prerequisite or isolate to a cleaner worker.
- `artifact_contract`: fix the template or serializer before trusting any result.
- `policy_safety`: stop immediately and return a blocked handoff.
- `human_input`: request the missing decision or manual evidence; do not guess.
- `waiting_input`: pause stall timing and request the missing input.
- `capability_context_debug`: escalate through the configured model ladder only after the packet and environment are known good.
- `unknown`: collect one more focused signal, then reclassify.

Default capability ladder:

```text
DeepSeek Flash strategy -> DeepSeek Pro strategy -> GPT-5.4 sub-agent -> Codex replan
```

This ladder applies only to `capability_context_debug`. No other `failure_class` should use capability escalation until its own layer has actually changed.

## Non-Count-Driven Escalation

Use failure class plus changed conditions as the escalation gate:

- `packet_definition`: rewrite or shrink the packet, then rerun once on the new packet.
- `routing_configuration` and `gateway_protocol`: change route or adapter configuration first, then rerun.
- `dependency_runtime` and `environment_runtime`: repair the local prerequisite first, then rerun.
- `human_input` and `waiting_input`: pause the worker lane until the missing decision or evidence arrives.
- `capability_context_debug`: move up the capability ladder only after packet and environment are already known good.

Retry counts may still be recorded in artifacts for auditability, but they are reporting fields, not routing policy.

## No-Retry Illusion

Repeated retries do not count as progress if they do not change the failure class. A second or third run is justified only when:

- the packet changed;
- the route changed;
- the environment changed;
- the artifact contract changed; or
- the human supplied the missing decision.
