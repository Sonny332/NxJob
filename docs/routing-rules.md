# External-Worker Routing Rules

This document routes default-off auxiliary external-worker failures. Codex remains the sole Controller. External workers cannot satisfy mandatory GPT-5.4 Implementer, Reviewer, or Release gates.

## Failure Classes

Classify every unsuccessful path before considering a retry.

| `failure_class` | Meaning | Typical examples |
| --- | --- | --- |
| `packet_definition` | Packet is ambiguous, oversized, or inconsistent. | unclear scope, missing stop condition, conflicting allowed files |
| `routing_configuration` | Selected provider route or model mapping is invalid or unavailable. | unresolved alias, bad model id, provider mismatch |
| `gateway_protocol` | Proxy/provider protocol is incompatible with the client shape. | Responses vs Chat Completions mismatch |
| `authentication` | Account access is absent, expired, or denied. | 401, 403, missing provider login |
| `dependency_runtime` | Required local runtime is unavailable or broken. | missing CLI, dependency import failure |
| `permissions_boundary` | Intentional access restrictions prevent execution. | denied path, blocked tool, secret-gated file |
| `environment_runtime` | Local environment prevents execution. | file lock, broken wrapper prerequisite |
| `artifact_contract` | Required status or report is malformed or missing. | invalid JSON, wrong terminal report |
| `policy_safety` | Packet would violate safety or repository rules. | auto-submit, push/release, production-data access |
| `human_input` | A human decision or observation is required. | approval gate, product decision, manual evidence |
| `waiting_input` | Worker is paused for a missing parameter or permission. | missing route choice, permission prompt |
| `capability_context_debug` | Worker cannot reason reliably across the approved packet. | repeated wrong assumptions despite complete evidence |
| `unknown` | Available evidence does not yet identify a stable class. | first-seen symptom |

## Retry Policy

Use this sequence:

1. Classify the failure.
2. Capture the smallest reliable evidence.
3. Change the narrowest responsible condition.
4. Retry once only when the packet, route, environment, artifact contract, or input materially changed.
5. If the retry fails, stop the external-worker path and hand reliable artifacts to the Controller.
6. If formal implementation is still needed, enter the normal GPT-5.4 Implementer gate as a separate workflow, not a third worker retry.
7. Switching external provider or model requires explicit user approval.

Retry count is an audit field, not permission to escalate. Repeating an unchanged packet is not progress.

## Class-Specific Response

- `packet_definition`: shrink or correct the packet.
- `routing_configuration`: correct the selected route or mapping; do not choose another provider/model without user approval.
- `gateway_protocol`: correct the proxy, adapter, or client protocol.
- `authentication`: stop and return the access blocker; never expose credentials in artifacts.
- `dependency_runtime`: stop and request any required installation or repair authorization.
- `permissions_boundary`: stop and ask whether the packet or boundary is wrong.
- `environment_runtime`: repair or isolate the specific environment condition. For Python tests, use the project pytest wrappers before any eligible retry.
- `artifact_contract`: correct the template or serializer before trusting output.
- `policy_safety`: stop immediately and return `failure_report.md`.
- `human_input` and `waiting_input`: stop or pause until the Controller supplies the missing decision or evidence.
- `capability_context_debug`: stop the current path. A different provider/model is a new user-authorized choice, not an automatic retry.
- `unknown`: collect one focused signal and reclassify before deciding whether the single retry is eligible.

## Terminal Routing

- `completed` writes only `implementation_report.md`.
- `stalled`, `blocked`, and `failed` write only `failure_report.md`.
- A completed external worker does not satisfy any mandatory native gate.
- A second unsuccessful worker attempt ends the auxiliary path.
