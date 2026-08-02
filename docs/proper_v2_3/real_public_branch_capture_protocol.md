# Real public branch capture protocol

## Scope

This protocol defines how the 12 frozen tau3 development candidates may be
converted into identical-start public branches. It is frozen before any target
task or acquisition model is run. The candidates remain development-only and
must never be described as held-out or confirmatory.

The protocol does not yet freeze a runtime, model, prompt, or endpoint and
therefore does not authorize capture execution.

## Public trajectory acquisition

Each pair receives exactly one acquisition attempt under the ordinary
`no_memory_baseline` agent condition. The interaction begins from the native
task start using the normal user simulator and public tools. Gold actions may
not be used to script a prefix. The capture layer may use evaluator-side pair
metadata to load the already frozen development task and identify the guarded
public tool name, but none of that metadata is sent to the agent, user
simulator, selector, memory lifecycle, ledger, or continuation controller.

The acquisition budget is 100 orchestrator steps and 10 tool errors. There is
no retry, resampling, replacement candidate, or post-output protocol change.

## Capture events

### Pre-action read-only

The branch is captured after the initial public user message and before the
first agent action. The environment checkpoint is fresh. No target tool call or
failure receipt is injected.

### Failed idempotent state setting

At the first public agent call matching the frozen guarded tool, native
execution is suppressed. The public receipt reports
`public_reference_epoch_changed`, `outcome=failed`, `retry_safe=true`, and
`verification_required=true`. The checkpoint is taken immediately before the
call. A verifier may copy only the declared entity argument from the public
call into the public read-only verifier; it receives no gold argument.

### Unknown non-idempotent outcome

At the first matching public call, the native action executes exactly once.
Its native result is withheld and replaced with a public `result_unknown`
receipt. The complete post-action checkpoint is captured, the call is marked
checkpoint-applied, and environment replay remains empty. Blind retry is
unsafe; only the declared public read-only verifier may resolve the ledger
entry.

## Failure preservation

Target-not-reached, invalid arguments, early user/agent termination, checkpoint
mismatch, or any duplicate native side effect stops the capture stage and is
preserved. The missing pair is not replaced and the acquisition is not rerun.
All 12 branches, including all eight post-failure branches, are required before
a later five-condition model protocol can be considered.

## Reporting and interpretation

The future manifest separately reports capture rate, target reach, branch
integrity, native executions, safety, agent cost, and user-simulator cost. A
passing capture would be infrastructure evidence only. It would not show
selector quality, lifecycle success, continuation, final task completion,
safety under a model comparison, or confirmatory generalization.

## Next gate

Freeze the complete acquisition runtime: exact agent and user-simulator models
and revisions, prompts, generation settings, seeds, tool adapter, receipt
serialization, task/environment hashes, cost endpoints, and stop/exclusion
rules. No model or task execution is authorized until that runtime passes a
CPU-only preparation validation in a separate commit.
