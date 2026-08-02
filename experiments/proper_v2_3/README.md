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
- `toolsandbox_five_condition_runner_adapter_v2_3.py`: maps public action
  contracts and visible execution history into the generic v2.3 controller.
- `toolsandbox_five_condition_provider_v2_3.py`: preserves the first four
  frozen providers and guards the fifth condition's complete trajectory.
- `validate_guarded_runner_v2_3.py`: scripted 12x5 ToolSandbox integration
  validation with deliberate successful-action repeat proposals.
- `run_guarded_runner_validation_remote_v2_3.py`: one-command CPU entry using
  the active remote `proper-toolsandbox` Python environment.
- `toolsandbox_qwen_five_condition_development_v2_3.py`: frozen 12x5 Qwen
  runner with endpoint-separated reporting and safety/completion stops.
- `run_qwen_five_condition_remote_v2_3.py`: CPU preflight followed by one GPU
  smoke and, only on smoke success, the remaining development pairs.
- `scripted_continuation_traces_v2_3.py`: no-model recovery handoff, progress
  stall, verification precedence, and evidence-boundary traces.
- `planbench_xl_capacity_audit_v2_3.py`: validates the prospective static
  source-qualification design and stops before inventory.
- `validate_execution_state_continuation_stage_v2_3.py`: one-shot CPU-only
  validation and SHA-256 envelope for the new design stage.
- `qualify_planbench_xl_source_v2_3.py`: verifies a frozen external checkout,
  regenerates the explicit blocker plan, and reports the full-capacity stop.
- `tau3_execution_state_continuation_screen_v2_3.py`: reconstructs the frozen
  complete ledgers and replays their public evidence through continuation.
- `validate_real_public_branch_capture_protocol_v2_3.py`: CPU-only validation
  of the one-attempt public acquisition, injection, isolation, and stop design;
  it is not a capture or model runner.

Preparation schema/validation protocol v2 preserves the failed fixed-path v1
manifest and writes every subsequent attempt to a unique run directory.
