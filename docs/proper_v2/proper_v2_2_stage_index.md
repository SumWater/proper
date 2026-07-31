# PROPER v2.2 lifecycle stage index

## Frozen development contract

- `memory_lifecycle_v2_2_protocol.md`
- `configs/proper_v2/memory_lifecycle_v2_2.yaml`
- `schemas/proper_v2/memory_lifecycle_v2_2.schema.json`
- `src/failure_memory/proper_v2/v2_2/`

## Validation

- `experiments/proper_v2/lifecycle_development_v2_2.py`: dependency-light
  lifecycle validation on the 12 development pairs;
- `experiments/proper_v2/toolsandbox_lifecycle_development_v2_2.py`:
  scenario-blind ToolSandbox apply/consume/handoff validation;
- `experiments/proper_v2/validate_proper_v2_2_lifecycle_stage.py`: one-shot
  unit, static, held-out-input, and ToolSandbox validation entry.

The full validation entry loads no language model and authorizes no GPU or
confirmatory claim.

## Completed Qwen development run

- `experiments/proper_v2/qwen_jsonl_worker_v2_2.py` adds prompt and completion
  token accounting;
- `experiments/proper_v2/toolsandbox_qwen_lifecycle_development_v2_2.py`
  removes consumed memory from subsequent prompts, enforces lifecycle guards,
  and reports selector, lifecycle, completion, safety, and cost separately;
- `configs/proper_v2/toolsandbox_qwen_lifecycle_development_v2_2.yaml` freezes
  its inputs.
- `toolsandbox_qwen_lifecycle_development_v2_2_results.md` records the
  development-only Qwen3-8B result and its interpretation boundary.

The run completed with 79/79 valid JSON decisions. All nine post-failure
memories were consumed and handed off to ordinary planning, but six
post-consumption prerequisite proposals required controller blocking and
post-failure completion remained 0/9. This is development evidence, not a
confirmatory result.

## Held-out preparation

- `experiments/proper_v2/toolsandbox_heldout_target_audit_v2_2.py`
- `configs/proper_v2/toolsandbox_heldout_target_audit_v2_2.yaml`
- `toolsandbox_heldout_target_audit_v2_2.md`

The current audit identifies two unconsumed non-source scenarios that require
CPU-only capacity screening. The completed screen is recorded in:

- `experiments/proper_v2/toolsandbox_unconsumed_capacity_v2_2.py`
- `configs/proper_v2/toolsandbox_unconsumed_capacity_v2_2.yaml`
- `toolsandbox_unconsumed_capacity_v2_2_protocol.md`
- `toolsandbox_unconsumed_capacity_v2_2_results.md`

Both targets are preservation-only: TF-IDF and PROPER select the same safe-stop
behavior, and the selected memory lacks a target-specific trigger match. No
model run on these two targets is authorized.
