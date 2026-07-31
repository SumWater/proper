# PROPER v2.3 first-stage index

## Method and policy

- `action_execution_contract.md`
- `target_capacity_audit_protocol.md`
- `configs/proper_v2_3/execution_controller_v2_3.yaml`
- `configs/proper_v2_3/target_capacity_audit_v2_3.yaml`

## Schemas

- `schemas/proper_v2_3/action_execution_ledger.schema.json`
- `schemas/proper_v2_3/controller_decision.schema.json`

## Implementation

- `src/failure_memory/proper_v2/v2_3/contracts.py`
- `src/failure_memory/proper_v2/v2_3/ledger.py`
- `src/failure_memory/proper_v2/v2_3/controller.py`

The implementation is scenario-independent and contains no model runner.

## Local validation

- `experiments/proper_v2_3/scripted_traces_v2_3.py`
- `experiments/proper_v2_3/target_capacity_audit_v2_3.py`
- `experiments/proper_v2_3/validate_proper_v2_3_stage.py`
- `tests/test_proper_v2_3_*.py`
- `tests/test_toolsandbox_v2_3_*.py`
- `first_stage_results.md`

The one-shot entry is CPU-only. It validates v2.3 tests, scripted traces,
frozen v1/v2 hashes, schemas, and the prospective capacity design. Its output
belongs under `outputs/proper_v2_3/first_stage_validation/`.

## Interpretation boundary

Passing this stage shows contract and controller consistency on scripted
development traces. It is not model behavior, final task-completion evidence,
held-out evidence, or authorization for GPU execution.

The existing 12 pairs remain available only for later development regression.
The current target-capacity decision remains zero new eligible targets.
