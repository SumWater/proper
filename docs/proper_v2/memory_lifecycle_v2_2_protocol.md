# PROPER v2.2 unified memory-lifecycle development protocol

## Status

This document freezes the first PROPER v2.2 lifecycle contract before any
v2.2 model output is generated. The 12 v2.1 Qwen pairs are development data
only. They cannot become a confirmatory v2.2 cohort.

The lifecycle is downstream of selection. It does not change which memory was
selected and must not be interpreted as additional selector evidence.

## State and interface

The same lifecycle interface is used for `pre_action` and `post_failure`.
Decision phase is recorded, but there is no scenario-family branch.

Every selected memory has one runtime state:

- `active`: the trigger holds or is not yet resolved, the memory is exposed,
  and the controller is memory-guided;
- `consumed`: success evidence or trigger clearance is verified, actionable
  memory content is removed, and control returns to ordinary task planning;
- `failed`: application failed or visible evidence conflicts after the retry
  budget, memory content is removed, and further tool use is stopped;
- `stopped`: the task completed, the Agent stopped, or a stop condition was
  observed.

Every transition records:

- whether trigger evidence `holds`, is `cleared`, or is `unknown`;
- whether runtime success evidence is `satisfied`, `violated`, or `unknown`;
- application and failed-attempt counts;
- remaining application attempts;
- exposure mode and injection weight;
- planning mode and machine-readable reason codes.

## Success and consumption

Source-trajectory evidence is provenance, not runtime success evidence. The
v2.2 controller therefore verifies public runtime evidence:

- an exact proposed recovery action completed without an exception;
- an explicit trigger-cleared observation;
- an Agent stop for a stop-and-report memory;
- or explicit task completion.

A successful recovery action with an explicitly still-active trigger is a
conflict and fails closed. A successful action without the required evidence
also fails closed. Once consumed, the default memory weight is zero and the
prompt contains no natural text or proposed action from that memory.

The lifecycle verifies completion of the memory-directed recovery operation.
It does not by itself establish final task completion.

## Retry and stopping

The frozen development maximum is two application attempts. A failed first
attempt may be retried while the trigger remains active. A second failed
attempt exhausts the budget and enters `failed`.

The controller blocks:

- a consumed memory's exact action from being called again without a newly
  active trigger and a new lifecycle;
- all tool calls after `failed` or `stopped`;
- tool calls while an active `stop_and_report` memory requires a safe stop.

## Development validation

Validation is split into distinct endpoints:

1. selector first-step behavior, inherited descriptively from frozen v2.1;
2. lifecycle transitions and memory removal;
3. ordinary-planning handoff;
4. final ToolSandbox task completion;
5. safety, including minefields and guard interventions;
6. cost, including model decisions, tool calls, exceptions, repeated calls,
   and lifecycle overhead.

The scripted v2.2 runner validates endpoints 2, 3, and controller-side safety.
Scripted decisions are not model behavior and do not establish endpoint 4.
A later Qwen development run may use the 12 pairs for debugging only.

## Held-out rule

Before confirmation, a target audit must exclude:

- all v2.1 model-exposed scenarios;
- memory-source semantic families;
- scenarios used to tune v2.2;
- behaviorally non-identifiable pairs.

If no eligible target remains, the audit must stop rather than relabel
development or preservation records as held-out confirmation.

No claim about all Agent-memory scenarios is authorized.
