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
- `validate_acquisition_runtime_feasibility_v2_3.py`: CPU-only audit of local
  agent/user interfaces, model revision, endpoint, prompt, and inventory
  readiness before an acquisition runtime can be frozen.
- `validate_local_tau_participant_adapter_v2_3.py`: runs the eight CPU-only
  agent/user message-contract tests and freezes their input hashes; it neither
  imports nor loads the local model.
- `validate_qwen_model_inventory_preparation_v2_3.py`: validates the local
  read-only inventory contract on temporary files.
- `run_qwen_model_inventory_remote_v2_3.py`: one-shot revision-guarded remote
  file inventory; it imports no model/tau package and performs no generation.
- `validate_qwen_model_inventory_result_v2_3.py`: locally freezes every
  returned inventory attempt and recomputes the successful manifest envelope.
- `scripted_acquisition_runtime_protocol_v2_3.py`: no-model traces for
  pre-action capture, both failure injections, duplicate safety, and stops.
- `validate_acquisition_runtime_protocol_v2_3.py`: validates 30 public tools,
  12 task hashes, frozen inputs, state-machine tests, traces, and closed gates.
- `synthetic_acquisition_jsonl_worker_v2_3.py`: persistent deterministic JSONL
  worker whose responses are explicitly synthetic and non-model.
- `run_acquisition_runtime_synthetic_cpu_v2_3.py`: fake-environment end-to-end
  runtime exercise for three effect classes and four deliberate failure paths.
- `validate_acquisition_runtime_implementation_v2_3.py`: verifies frozen
  implementation hashes, closed schemas, 11 scoped tests, 15 synthetic checks,
  participant privacy, and no tau/model/task/GPU use.
- `validate_acquisition_one_shot_runner_protocol_v2_3.py`: CPU-only validator
  for the future remote environments, first-pair smoke, early-stop envelope,
  frozen hashes, and still-closed execution gates. It is not the real runner.
- `run_tau3_acquisition_remote_v2_3.py`: revision-guarded, one-attempt remote
  Qwen/tau3 acquisition runner with full preflight and atomic partial results.
- `validate_acquisition_one_shot_runner_implementation_v2_3.py`: CPU-only
  implementation/hash/test gate before the single remote command.
- `validate_tau3_acquisition_preflight_failure_v2_3.py`: freezes the returned
  dirty-worktree-only preflight failure and its zero-execution boundary.
- `validate_tau3_acquisition_result_v2_3.py`: hashes and audits the preserved
  five-attempt stopped result, including raw-record cost reconciliation; it is
  not a model runner and cannot authorize a rerun.
- `validate_appworld_source_qualification_design_v2_3.py`: CPU-only validation
  of the prospective AppWorld source, license, exposure, action-interception,
  hidden-evaluator, and closed execution boundaries; it acquires no source.
- `validate_appworld_offline_wheel_inventory_preparation_v2_3.py`: validates
  the exact PyPI identity, safe wheel reader, synthetic tests, schemas, and
  no-install boundary before one external-wheel inventory.
- `run_appworld_offline_wheel_inventory_remote_v2_3.py`: guarded read-only
  inventory of one user-supplied wheel outside the project; it performs no
  download, import, installation, extraction, or decryption.
- `validate_appworld_wheel_inventory_result_v2_3.py`: freezes the unique
  returned inventory and recomputes member paths, totals, canonical manifest,
  protected bundle records, and closed execution gates.
- `scripted_appworld_controlled_install_protocol_v2_3.py`: six no-decryption
  traces for exact apps-bundle handling, archive attacks, plaintext leakage,
  tests-bundle access, and forbidden official commands.
- `validate_appworld_controlled_install_protocol_v2_3.py`: validates the
  controlled-install design and keeps decryption, extraction, API inventory,
  model, and GPU gates closed.
- `run_appworld_apps_bundle_inventory_remote_v2_3.py`: guarded one-shot
  in-memory decryption and aggregate/hash-only inventory of the exact apps
  bundle; it never extracts protected source.
- `validate_appworld_apps_bundle_inventory_implementation_v2_3.py`: validates
  implementation hashes, schemas, synthetic attacks, plaintext exclusion, and
  the single remote inventory gate.
- `validate_appworld_apps_bundle_inventory_preflight_failure_v2_3.py`: freezes
  the missing-`cryptography` preflight result and keeps decryption and retry
  closed while authorizing dependency-provisioning design only.
- `run_appworld_offline_dependency_repair_remote_v2_3.py`: verifies and installs
  the three pinned wheels into a new external target, probes versions, and
  invokes the unchanged inventory once without network access.
- `validate_appworld_offline_dependency_repair_v2_3.py`: CPU-only hash,
  no-network, non-overwrite, dependency-chain, and single-invocation gate.
- `validate_appworld_apps_bundle_inventory_result_v2_3.py`: freezes both remote
  artifacts and recomputes aggregate counts, bytes, hashes, and claim gates.
- `scripted_appworld_static_api_protocol_v2_3.py` and
  `validate_appworld_static_api_protocol_v2_3.py`: eight synthetic decisions
  and a CPU-only design gate before implementation.

Preparation schema/validation protocol v2 preserves the failed fixed-path v1
manifest and writes every subsequent attempt to a unique run directory.
