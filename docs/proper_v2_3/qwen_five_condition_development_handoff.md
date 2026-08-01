# PROPER v2.3 Qwen five-condition development handoff

This is the first and only authorized v2.3 model run for the frozen protocol.
It uses the original 12 model-exposed development pairs and is neither held-out
nor confirmatory.

The launcher first runs six CPU-only runner-contract tests. Only if they pass
does it start a one-pair GPU smoke test. Invalid smoke output stops before the
remaining 11 pairs. A successful smoke continues in the same process with the
same provider and model worker.

The five conditions, Qwen3-8B path, deterministic decoding, prompts, four
independent controller budgets, evaluation endpoints, exclusions, and stop
rules are frozen in
`configs/proper_v2_3/toolsandbox_qwen_five_condition_development_v2_3.json`.

The result reports selector, lifecycle, continuation, completion, safety, and
cost separately. It is retained even when a stage gate fails. The stage stops
without retuning this protocol if:

- a duplicate non-idempotent side effect executes;
- post-failure completion is not strictly better than condition four;
- ledger/accounting integrity fails; or
- the GPU smoke test fails.

Every attempt writes a unique `results.json` under
`outputs/proper_v2_3/qwen_five_condition_development_remote/`.
