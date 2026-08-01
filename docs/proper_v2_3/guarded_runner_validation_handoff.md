# PROPER v2.3 guarded runner CPU validation

This gate validates the complete-trajectory ToolSandbox adapter before any
Qwen or GPU execution. It uses the passed 12-pair, five-condition preparation
at SHA-256 `f7f29d03753423351f49f4790ecd18d3c767a1bb3f0f073dccbfa7532768c85a`.

The first four conditions retain the frozen execution-engine behavior. The
fifth condition routes every proposed tool action through the generic v2.3
controller and records prefix actions, proposals, executions, outcomes, and
blocked proposals in one `ActionExecutionLedger`.

The scripted provider intentionally proposes exact repeats after successful
actions. These are validation probes, not model outputs. A passing run must:

- execute all 12 pairs and all 60 conditions from identical branch starts;
- resolve every allowed ledger entry against visible ToolSandbox history;
- record and block at least one successful-action repeat proposal;
- exercise a blocked non-idempotent proposal and execute no duplicate
  non-idempotent side effect;
- include the pre-controller branch prefix in the trajectory ledger;
- find no scenario, semantic-family, gold, or evaluator branch token in the
  v2.3 adapter/provider method sources;
- pass exactly 80 scoped v2.3 tests.

Run this only in the remote machine's active `proper-toolsandbox` environment.
It sets `CUDA_VISIBLE_DEVICES=-1` and neither imports a model worker nor reads
model outputs. Every attempt writes a new directory under
`outputs/proper_v2_3/guarded_runner_validation_remote/`; failed attempts are
retained.

After a passing result, the next gate is to freeze the real five-condition
Qwen runner and its one-shot development command. A passing CPU validation
does not itself authorize that GPU run.
