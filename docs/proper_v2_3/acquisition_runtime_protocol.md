# Acquisition runtime protocol

This stage freezes the complete local-Qwen branch-acquisition protocol before
runtime implementation or any model load. It joins the previously frozen
public capture semantics, participant adapter, exact Qwen content manifest,
pinned tau source, 12 development tasks, and future capture-manifest schema.

## Complete public-tool boundary

The runtime registry covers all decorated public tools in the pinned airline
and retail domains: 14 airline tools and 16 retail tools. It is deliberately
broader than the earlier guarded/verifier registry. In particular,
`get_flight_status` is now explicitly classified as read-only even though it
did not occur in the selected evaluator action proxies used by source
qualification. Unknown tools stop before native execution.

The complete ledger records every proposed and executed tool call before the
capture target. Repeated read-only calls remain allowed. An identical
state-changing signature whose prior outcome is successful or unknown is
blocked before a second native execution, for both idempotent state settings
and non-idempotent side effects. Ambiguous non-target outcomes stop and retain
the checkpoint; they are never retried.

## Turn and capture semantics

The half-duplex loop starts with the local Qwen user simulator. A public user
message routes to the agent; an agent message routes to the user; a single
agent tool call routes through the environment and returns to the agent. The
agent and user use one persistent local worker with separate system prompts.
Parallel tool calls, invalid-output retries, worker restarts, external APIs,
and resampling are disabled.

Pre-action branches capture after the first nonterminal public user message
and before any agent request. An idempotent target is checkpointed before its
proposal, suppressed, and receives `public_reference_epoch_changed`. A
non-idempotent target executes exactly once, its native result remains hidden,
the post-effect state is checkpointed, and participants receive
`result_unknown`. Capture stops immediately after the public receipt.

`###STOP###`, `###TRANSFER###`, and `###OUT-OF-SCOPE###` are observable user
termination tokens. A terminating initial user message is an early-termination
capture failure, not a pre-action branch. Invalid JSON, worker errors, unknown
tools, budget exhaustion, target non-reach, checkpoint failure, or unsafe
duplicate proposals are preserved and stop the complete 12-pair stage. No pair
is retried, resampled, or replaced.

## Frozen inputs, budgets, and reporting

All 12 full task records, private user scenarios, initial states, and
evaluator-only criteria have separate canonical hashes. Task IDs, target
actions, evaluator hashes, recoverability, and evaluator outcomes remain in
the routing layer and never enter worker messages. Domain task files, policies,
databases, simulation guidelines, tau revision, participant prompts, worker,
adapter, model inventory, and output schema are also hashed.

Per-pair caps separately cover orchestrator events, tool errors, agent/user
requests, prompt tokens per request, total prompt tokens, total completion
tokens, invalid decisions, and worker errors. Reporting separates agent and
user request/prompt/completion tokens, native tool executions, target native
execution, tool errors, steps, and wall-clock time. Token counts are local
cost endpoints; no unsupported dollar price is inferred.

CPU validation covers 30/30 public tools, 12/12 task-component hashes, twelve
state-machine unit tests, and eight scripted trace checks. It loads no model,
executes no tau task, reads no model output, and uses no GPU. Passing authorizes
implementation of the acquisition runtime plus a synthetic CPU dry-run only.
It does not authorize loading Qwen, capturing branches, running the 12 tasks,
implementing a comparison runner, or making confirmatory claims.
