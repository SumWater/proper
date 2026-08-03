# One-shot acquisition runner implementation

## Result

The remote tau3 acquisition runner is implemented and passes CPU-only local
validation. Sixteen validation checks and 24 scoped tests pass. The tests cover
all 12 synthetic pair positions, all three effect classes, atomic attempt
persistence, progress-envelope refresh, exact task-component hashes, lazy
imports, fail-closed preflight, and a deliberate invalid fifth attempt that
prevents the sixth attempt from starting.

No tau3 runtime or model library is imported at runner-module import time. The
validation loads no model, reads no model output, executes no task, and uses no
GPU. The implementation-config SHA-256 is
`7b5dfab1fdc5abda07c74570ab94cbbb04573012467fc00549fc0d0f5c6cf3fa`;
the validation-envelope SHA-256 is
`025dc3aa1637cf8db0973b780732e2e1dac97155c5d90b1ea9909a870a343579`.

## Pre-model corrections

Two representational/test-lifecycle corrections are explicit and occur before
any real model output:

1. The frozen run-envelope v1 capped the complete trajectory's native tool
   count at one. A post-failure branch may legitimately execute multiple
   ordinary tools before reaching its target. Run-envelope v2 therefore leaves
   `native_tool_execution_count` uncapped and separately caps
   `target_native_execution_count` at one. V1 remains unchanged.
2. The protocol-design test permanently asserted that the future runner file
   did not exist. It is now monotonic: before implementation it requires
   absence; after implementation it requires the runner's exact hash in the
   implementation config. The frozen protocol validation output is unchanged.

The first-response timing endpoint is named
`model_startup_to_first_response_seconds`: it is an observable upper bound that
includes worker startup, model load, and the first generation. It is not
misreported as pure model-load time.

## Runtime behavior

The runner creates the unique output directory before expensive inventory
work, so preflight failures and interruptions can be preserved. It then checks
the exact project revision and clean tracked worktree, all frozen input hashes,
tau revision and 32-file execution manifest, domain data and 12 task-component
hashes, the complete 15-file Qwen inventory, both Python environments, and CUDA
device visibility.

Only a passing preflight starts one persistent Qwen worker. `tau3-dev-01` is
the only smoke attempt for that pair. Every later pair receives a fresh tau3
environment. Each attempt is atomically written and hashed, and `result.json`
is atomically refreshed after every attempt. The first non-captured branch,
invalid output, worker/environment failure, safety failure, or interruption
stops the stage. There is no retry, restart, resume, rerun, replacement, or
resampling.

The result distinguishes observable model response, model output read, task
attempt, and GPU use. Starting a child process without observing a model
response is not reported as a successful model load.

## Interpretation

This validation authorizes exactly one guarded remote acquisition command. The
12 targets remain development-only, not held-out or confirmatory. A successful
12/12 acquisition would authorize design of a separate tau3 five-condition
model protocol; it would not itself establish selector, lifecycle,
continuation, completion, safety, or cost improvement.
