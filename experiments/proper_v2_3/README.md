# PROPER v2.3 experiments

This directory is reserved for scenario-independent preparation, capacity
audit, scripted validation, and guarded model-development entry points.

Do not write new results into `outputs/proper_v2/`. Remote work must be
packaged as one complete local stage with one folder-level sync and one guarded
command.

- `scripted_traces_v2_3.py`: dependency-light multi-step regression traces;
- `target_capacity_audit_v2_3.py`: validates the no-model/no-play prospective
  capacity design and retains the current no-capacity stop;
- `validate_proper_v2_3_stage.py`: one CPU-only local validation entry.
- `prepare_five_condition_development_v2_3.py`: expands the immutable v2.2.1
  12x4 manifest to a same-start 12x5 manifest without reading model-output
  content or executing a target.
- `validate_five_condition_protocol_v2_3.py`: CPU-only one-shot preparation,
  schema, frozen-hash, and 72-test validation. It is not a model runner.
- `run_five_condition_preparation_remote_v2_3.py`: isolated-environment,
  revision-guarded, CPU-only remote bootstrap for that validation.
