# PROPER v2.3 five-condition development protocol

## Status and scope

This protocol is frozen before any PROPER v2.3 model output. It prepares a
same-start, five-condition Qwen3-8B development regression on the 12
ToolSandbox pairs already exposed in v2.1, v2.2, and v2.2.1. Those pairs remain
development-only and can never be described as held-out or confirmatory.

The 12 tau3 train pairs are not mixed into this comparison. Their passed
remote CPU screen supplies cross-effect-class scripted branch-capacity
evidence only. It does not supply selector or model-completion evidence.

This stage freezes preparation and validation artifacts. It does not implement
or execute a model runner, load a model, use a GPU, play a target scenario, or
authorize a confirmatory claim.

## Five conditions

Every pair begins from the byte-identical frozen v2.2.1 branch request for all
four PROPER conditions. The condition order is fixed:

1. `tfidf_rank1_memory`: TF-IDF rank-1 memory remains persistent;
2. `proper_v2_1_memory`: unified PROPER memory remains persistent;
3. `proper_lifecycle_prompt_only`: PROPER memory is consumed and removed;
4. `proper_lifecycle_replan_controller`: the frozen v2.2.1 controller blocks
   only exact repeats of the consumed recovery action;
5. `proper_v2_3_full_ledger_controller`: the same selector and lifecycle use
   the complete v2.3 ActionExecutionLedger for every proposed and executed
   action in the trajectory.

The contrasts are interpreted separately: 1 versus 2 is selector; 2 versus 3
is lifecycle; 3 versus 4 is recovery-action continuation; 4 versus 5 is full
trajectory execution control. No single aggregate score may replace these
contrasts.

## Method boundary

The fifth condition accepts only the common observable interface:

```text
ObservableRecoveryState
+ selected MemoryPolicyCard
+ MemoryLifecycleState
+ ActionExecutionLedger
-> allow | verify | replan | stop
```

The method may receive public tool schemas, declared action-effect and
retry-safety evidence, visible tool outputs or exceptions, and ledger state.
It must not receive scenario name, semantic family, benchmark recoverability,
gold action, gold label, evaluator outcome, task ID, or prior model result.
Evaluator metadata remains evaluation-side only.

The action-effect taxonomy and retry contract are frozen in
`execution_controller_v2_3.yaml`. The 17 tools exposed by the frozen cohort are
classified once, from public names, descriptions, and schemas, in
`toolsandbox_action_effect_contracts_v2_3.json`; this is a tool-contract
registry, not a scenario branch. Unregistered actions remain `unknown_effect`
and stop closed. All proposals enter the ledger. Successful
actions and outcome-unknown side effects cannot execute again. Unknown effects
fail closed. Outcome-unknown non-idempotent actions require a declared
read-only verification path and cannot be retried before resolution.

## Prompts and controller feedback

The initial model request is copied without modification from the frozen
v2.2.1 prepared manifest. The fifth condition therefore cannot obtain an
initial-prompt advantage. Controller feedback is a canonical structured JSON
payload using the exact fields and instructions frozen in
`five_condition_prompts_v2_3.json`.

Blocked attempts remain model requests and are included in cost. `allow`
executes the proposed action, `verify` executes only the declared read-only
verification action, `replan` sends non-executing feedback, and `stop`
terminates without being relabelled task completion.

## Independent budgets

The native Agent trajectory retains the frozen v2.2.1 limits of four decisions
and four tool calls after the branch. The v2.3 controller independently has:

- retry budget: 1;
- verification budget: 2;
- invalid-decision budget: 1;
- replan budget: 2.

Consuming one budget cannot decrement another. Verification tool calls count
as tool calls and controller overhead. A budget exhaustion produces an
observable fail-closed stop reason.

## Endpoint-separated evaluation

Results must report phase and condition separately, with raw per-pair records:

- selector: first-decision policy alignment;
- lifecycle: active/consumed/failed/stopped transitions, trigger evidence,
  success evidence, and ordinary-planning handoff;
- continuation: consumed recovery-action proposals, executions, blocks,
  accepted replans, and exhausted replans;
- completion: native final similarity, completion at similarity one, and
  partial milestone progress;
- safety: every repeated proposal and execution split into read-only,
  idempotent state-setting, non-idempotent side effect, and unknown effect;
  duplicate non-idempotent effects, outcome-unknown actions, verification
  outcomes, tool exceptions, minefields, and controller interventions;
- cost: model requests, accepted decisions, native tool calls, verification
  calls, prompt tokens, completion tokens, total tokens, and controller-added
  requests/tokens/tool calls.

Token and operation counts are not latency, energy, or monetary cost. Early
stopping cannot be called efficient without reporting completion and safety.

## Prespecified stop rules

Run the frozen 60 conditions once. Preserve all outputs, including failures.
Do not tune this protocol after seeing its model outputs.

Stop v2.3 development on this cohort without parameter tuning if any of the
following occurs:

1. the fifth condition executes any repeated non-idempotent side effect;
2. an outcome-unknown non-idempotent action is retried before successful
   read-only verification;
3. the fifth condition completes no more post-failure tasks than the frozen
   v2.2.1 controller condition in the same run;
4. any frozen input hash, same-start identity, request log, ledger transition,
   or evaluator accounting check fails;
5. model output is used to change this protocol and the same 12 pairs are then
   presented as confirmation.

The first two are safety stops. The third is the prespecified completion stop.
Failures must still be reported across selector, lifecycle, continuation,
completion, safety, and cost.

## Authorization boundary

A passing preparation validation authorizes only creation of a separate,
guarded remote development runner in a later commit. It does not itself
authorize GPU execution. GPU authorization requires that runner, its model
worker, request/response schemas, evaluation adapter, complete input hashes,
and one-shot remote command to be reviewed and frozen before use.

No result on these 12 pairs can authorize a confirmatory claim. New held-out
capacity remains zero.
