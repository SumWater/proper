# PROPER v2.3 execution-state continuation design

## Status and motivation

This is a prospective CPU-only design stage after the frozen five-condition
Qwen development result at revision
`e84772a6d703bb08a069c57c9c8d370769de73c5`. It does not alter or rerun that
protocol. The existing 12 pairs remain development-only and are not authorized
for another tuned model comparison.

The frozen result separated two findings: the complete action ledger removed
identical successful-action repeats and duplicate non-idempotent executions,
but all 9 post-failure tasks remained incomplete. The missing mechanism is
therefore modeled as recovery continuation: after a recovery memory is
consumed, the agent needs an observable representation of completed and
remaining subgoals rather than another persistent recovery instruction.

## Interface

The design adds one layer above the existing v2.3 controller:

```text
ControllerState
+ ActionExecutionLedger
+ ExecutionProgressState
+ ObservableProgressEvidence
-> continue | verify | revise | stop
```

`ExecutionProgressState` contains ordered subgoal contracts, one active
subgoal, consecutive no-progress count, the last verified evidence, and any
ledger entries whose effects remain uncertain. Each subgoal declares its
success-evidence codes before execution.

## Observable-evidence boundary

Progress may be established only by a tool result, public state query, or
public environment contract. Agent self-report is insufficient. Scenario
names, semantic families, recoverability labels, gold actions or paths,
evaluator outcomes, and prior model results are forbidden method inputs.

Benchmark gold fields may be used only after execution by the evaluator or in
an input-only capacity audit. They cannot produce the agent-facing subgoal
state or success evidence.

## State transitions

1. Any allowed ledger entry still in `executed` or `outcome_unknown` routes to
   `verify` before continuation.
2. Declared evidence completing the active subgoal marks it `completed`,
   activates the next pending subgoal, resets the stall count, and routes to
   `continue`.
3. An observation without declared subgoal evidence increments the stall
   count. Before the threshold it remains a bounded `continue`.
4. At the threshold, an available existing replan budget is consumed and the
   controller routes to `revise` at the current subgoal boundary. The stall
   counter resets, giving the revised plan a bounded cooldown window before a
   later revision can be requested.
5. A stall with no replan budget fails closed with `stop`.
6. Task completion is accepted only after all declared subgoals have observable
   success evidence; it cannot bypass unfinished subgoals.

The existing retry, verification, invalid-decision, and replan budgets remain
independent. This layer adds no shared retry counter and uses the controller's
existing replan budget.

## Interpretation boundary

Passing unit tests or scripted traces establishes internal consistency only.
It does not show improved model completion, generalization, or confirmatory
evidence. A model experiment requires genuinely unconsumed targets, frozen
input hashes and partitions, a base-capability gate, and a new protocol frozen
before any model output.

The design is informed by execution-state memory, workflow memory, grounded
plan correction, and progress-gated recovery literature. Those works motivate
the representation; they do not establish that this implementation will
improve PROPER.
