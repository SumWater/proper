# One-shot tau3 acquisition-runner protocol

## Purpose

This stage freezes how a future remote runner may acquire the 12 development
branches. It does not implement that runner and does not authorize its command,
model loading, task execution, branch capture, or GPU use.

The project orchestration process and Qwen worker deliberately use separate
Python environments. The lightweight project process owns the pinned tau3
environment and observable execution ledger. The existing
`failure-memory-pilot` worker process owns Qwen3-8B. They communicate through
the already validated sequential JSONL boundary; agent and user requests share
one persistent worker but keep separate prompts and participant histories.

## Preflight and execution order

Before the worker starts, the future runner must verify the exact project
revision, clean tracked worktree, absent unique output directory, every frozen
project input, tau3 revision and source manifest, domain data hashes, full Qwen
file inventory, both Python environments, and CUDA device visibility. A failed
preflight writes an envelope and loads no model.

`tau3-dev-01` is the smoke pair because it ends at a pre-action capture before
any agent request or native tool effect. Its capture is its sole allowed
attempt, not a disposable extra run. On success, pairs 02 through 12 continue
in the same process and worker. Every pair receives a fresh environment.

There is no invalid-output retry, worker restart, failed-pair rerun, interrupted
run resume, candidate replacement, or resampling. The first non-captured pair
stops the complete stage. A non-idempotent native effect may execute at most
once in its pair.

## Versioned early-stop envelope

The frozen v1 capture-manifest schema required exactly 12 attempt records while
the frozen failure policy stopped after the first uncaptured pair. That made a
legitimate early-stop result impossible to represent. The v1 schema is kept
unchanged. `real_public_branch_capture_run.schema.json` is the versioned run
envelope and permits zero attempts for preflight failure or 1–12 actual attempt
artifacts thereafter.

Each attempt is atomically written and content-hashed immediately. The stage
summary is atomically refreshed after each attempt. Partial results, raw worker
text and usage, checkpoints, complete ledgers, and worker stderr are retained.
An interruption is final for this protocol; it is preserved and not resumed or
rerun.

## Pass and interpretation

Passing requires 12/12 captures, 8/8 post-failure captures, zero duplicate
non-idempotent executions, valid attempt/checkpoint hashes, and complete cost
endpoints. A passing acquisition would authorize design of a separate tau3
five-condition model protocol only. It would not itself measure selector,
lifecycle, continuation, completion, or general Agent-memory performance.

These targets remain development-only and already exposed to offline design.
They are neither held-out nor confirmatory. All failures and costs remain part
of the record.

The next permitted stage after CPU validation is local implementation and
synthetic/preflight validation of the one-shot runner. The command template is
frozen in the configuration, but executing it remains forbidden until that
later runner-validation stage passes and a separate handoff is created.

The protocol-config SHA-256 is
`ad5fb6a719969aa1dde6a9ba4d88d3d5683eb543f11ebee3fc81d7104e5d5668`;
the CPU validation-envelope SHA-256 is
`52443099f6e6270e124e412bb841e45f3ed726f166f0076e8f2e6be1354353b4`.
