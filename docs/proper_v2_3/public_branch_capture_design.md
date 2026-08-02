# Public branch capture and identical-start replay

## Purpose

This CPU-only design closes the gap found by the tau3 model-protocol
feasibility audit. It defines how to preserve an observable branch for all
experimental conditions without leaking evaluator metadata and without
reexecuting a successful or outcome-unknown side effect during initialization.

It is scenario-neutral. No scenario name, semantic family, task ID, gold
action, recoverability label, or evaluator outcome is used by the method.

## Two-state separation

A branch boundary contains two deliberately separate views:

1. Participant state: complete public user, assistant, tool-call, and tool-result
   history, plus the controller state built from that public evidence.
2. Evaluator/runtime state: an environment checkpoint, its digest, and the call
   IDs whose effects are already represented in that checkpoint.

The method receives only the first view. The environment checkpoint is never a
prompt or controller input.

## Replay rule

The participant message history remains complete so the agent and user resume
from the same observable conversation. The environment is restored from the
complete checkpoint and receives an empty history for mutation replay. The
runtime adapter must therefore initialize participant histories and environment
state through separate channels instead of passing the same history to tau3's
default `Environment.set_state()`.

This distinction is mandatory for unknown outcomes. If a non-idempotent action
executed and its response was replaced by a public `result_unknown` receipt,
replaying the visible call against the restored environment would duplicate the
side effect. The call ID is instead marked checkpoint-applied and skipped.

## Integrity

`identical_start_sha256` covers the complete public history, environment
checkpoint digest, and controller state. Every experimental condition must
receive the same digest. Any history, checkpoint, or controller-state change
creates a different start hash.

## Scripted evidence and limits

Three CPU traces cover a read-only pre-action trigger, an idempotent setting
that fails without execution, and a non-idempotent action that executes with an
unknown public result. All five planned development conditions share one start
hash per trace, and the unknown side effect is not replayed.

These traces authorize only implementation of a CPU-only tau3 runtime adapter.
They do not create the missing eight real branches, execute a target task,
authorize a model runner, or provide completion, safety, cost, held-out, or
confirmatory evidence.
