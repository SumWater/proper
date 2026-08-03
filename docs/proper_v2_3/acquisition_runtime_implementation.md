# Acquisition runtime implementation and synthetic CPU validation

## Scope

This stage implements the already frozen acquisition-runtime protocol without
loading a model, importing tau3 at validation time, executing a benchmark task,
or using a GPU. It validates transport, participant separation, environment
checkpointing, complete-ledger duplicate control, persistence, and fail-closed
stops using synthetic inputs only.

The frozen protocol-v1 files and their validation result remain unchanged. Two
limitations discovered while translating that simulator into an executable
runtime are corrected in this new implementation layer before any model or
task output exists:

1. a `pre_action` artifact records the hash and payload of the actual initialized
   environment checkpoint instead of the simulator's placeholder hash;
2. an ambiguous non-target state-changing result is replaced by the public
   `result_unknown` receipt, the post-action checkpoint is saved, and the
   attempt stops immediately.

These are integrity and safety corrections, not post-result protocol tuning.

## Components

- `acquisition_runtime.py` defines the half-duplex JSONL worker port,
  environment port, attempt specification, one-attempt loop, and atomic
  stage persistence.
- `tau3_acquisition_runtime_adapter.py` contains the lazy pinned-source tau3
  namespace, public tool-contract normalization, database checkpointing, and
  native tool execution boundary. Importing it does not import tau3 or model
  libraries.
- `synthetic_acquisition_jsonl_worker_v2_3.py` is a persistent deterministic
  worker whose outputs are explicitly marked as synthetic and non-model.
- `run_acquisition_runtime_synthetic_cpu_v2_3.py` exercises the complete
  transport and runtime using an in-memory fake environment.
- `validate_acquisition_runtime_implementation_v2_3.py` verifies hashes,
  schemas, closed gates, tests, and the synthetic result envelope.

The worker sees only the participant-specific prompt, canonical public
history, and public tool contracts. Pair/task routing and the private user
scenario remain outside worker request identifiers and public messages. Agent
and user roles use separate prompts and histories even though a future remote
run may share one sequential worker process.

## Synthetic coverage

Three successful fixtures cover all effect classes needed by the acquisition
protocol:

- a read-only `pre_action` capture backed by the actual checkpoint;
- a target idempotent setting proposal suppressed before native execution;
- a target non-idempotent action executed once with its native result hidden.

Four deliberate failures are retained as structured results:

- invalid JSON with zero response retry;
- worker error with zero worker restart;
- ambiguous non-target write with checkpoint-and-stop;
- a repeated successful state change blocked before a second native execution.

The validation passes 11 scoped tests without resource warnings and 15
synthetic end-to-end checks. The synthetic dry-run SHA-256 is
`add4254f16d193f342ac3b5255b90537ee49a265a42f914c4d4bd278009d3caf`.
The validation-envelope SHA-256 is
`09b1e92e85a2103f25f7024a7ce7cd97717bec366a46ab3b3a4fff0e16634b72`.

## Interpretation and next gate

This is implementation evidence only. It says that the runtime obeys the
frozen observable-evidence, persistence, and safety contracts on scripted
inputs. It provides no selector, lifecycle, continuation, completion, safety,
cost, held-out, or confirmatory model result.

The only newly authorized activity is design and freeze of a separate one-shot
real acquisition-runner protocol. Model loading, the 12 development attempts,
real branch capture, comparison-runner work, external APIs, GPU use, and
confirmatory claims remain closed until that later protocol is reviewed and
frozen.
