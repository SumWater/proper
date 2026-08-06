# PROPER v2.3 schemas

This directory is reserved for the action-effect, execution-ledger, controller
decision, and version-specific result schemas. Frozen schemas under
`schemas/proper_v2/` remain read-only.

- `action_execution_ledger.schema.json`: complete-trajectory proposed,
  executed, succeeded, failed, and outcome-unknown records.
- `controller_decision.schema.json`: unified allow/verify/replan/stop decision
  and independent remaining budgets.
- `five_condition_manifest.schema.json`: frozen 12x5 prepared-manifest and
  fifth-condition observable-ledger contract.
- `five_condition_preparation_validation.schema.json`: closed CPU preparation
  validation envelope with 72-test and no-model authorization boundaries.
- `guarded_runner_validation.schema.json`: closed scripted integration result
  with an 80-test contract and explicit no-model/no-GPU boundary.
- `qwen_five_condition_result.schema.json`: top-level smoke or complete Qwen
  development-result envelope; partial smoke failures remain serializable.
- `execution_progress_state.schema.json`: ordered observable subgoal state,
  verified evidence, uncertainty, stall count, and terminal reason.
- `continuation_decision.schema.json`: continue/verify/revise/stop envelope
  joining progress state with the existing controller state.
- `real_public_branch_capture_manifest.schema.json`: closed future output for
  12 one-attempt public branch acquisitions, including integrity, execution,
  cost, and preserved failure fields.
- `acquisition_runtime_feasibility.schema.json`: closed negative or ready audit
  for agent/user interfaces, model revision, endpoint, and model/GPU gates.
- `acquisition_participant_decision.schema.json`: exclusive strict JSON
  message-or-public-tool decision contract for the local participant adapter.
- `qwen_model_inventory.schema.json`: closed successful or stopped remote
  per-file SHA-256 inventory envelope with explicit no-execution claims.
- `qwen_model_inventory_freeze.schema.json`: closed local result-freeze
  envelope preserving failed preflights and the successful content identity.
- `acquisition_runtime_protocol_validation.schema.json`: closed CPU protocol
  validation envelope before runtime implementation or any model execution.
- `acquisition_runtime_synthetic_dry_run.schema.json`: closed synthetic
  end-to-end result including fixtures, request counts, execution counts,
  privacy checks, and explicit non-model boundaries.
- `acquisition_runtime_implementation_validation.schema.json`: closed
  implementation validation and next-gate envelope.
- `real_public_branch_capture_run.schema.json`: versioned remote-run envelope
  that preserves zero-attempt preflight failures and 1–12 actual attempts.
- `acquisition_one_shot_runner_protocol_validation.schema.json`: closed
  CPU-only runner-protocol design validation envelope.
- `real_public_branch_capture_run_v2.schema.json`: corrected remote result
  envelope separating complete-trajectory and target native-execution counts.
- `acquisition_one_shot_runner_implementation_validation.schema.json`: closed
  CPU implementation-validation and remote-authorization envelope.
- `tau3_acquisition_preflight_failure_freeze.schema.json`: closed local freeze
  of a zero-attempt infrastructure preflight failure and retry disposition.
- `tau3_acquisition_result_freeze.schema.json`: closed integrity and audit
  envelope for the stopped five-attempt acquisition result, with the
  scientific-stage and rerun gates fixed false.
- `appworld_source_qualification_design.schema.json`: closed no-source,
  no-inventory, no-task, no-model validation envelope for prospective
  AppWorld qualification design.
- `appworld_offline_wheel_inventory.schema.json`: closed passing or stopped
  exact-wheel inventory with member hashes and explicit no-extraction gates.
- `appworld_offline_wheel_inventory_preparation.schema.json`: closed CPU-only
  preparation result before the single read-only wheel inventory.
- `appworld_wheel_inventory_result_freeze.schema.json`: closed local freeze of
  the successful 44-member wheel inventory and protocol-design-only authority.
- `appworld_controlled_install_static_inventory_protocol_validation.schema.json`:
  closed no-decryption design result before aggregate-only bundle-inspector
  implementation.
- `appworld_apps_bundle_inventory.schema.json`: closed successful or stopped
  aggregate/hash-only protected bundle inventory without plaintext paths.
- `appworld_apps_bundle_inventory_implementation_validation.schema.json`:
  closed synthetic implementation gate before one real in-memory inventory.
- `appworld_apps_bundle_inventory_preflight_failure_freeze.schema.json`:
  closed freeze of the dependency preflight result before any decryption.
- `appworld_offline_dependency_repair.schema.json`: closed provisioning and
  delegated-inventory result with explicit stop outcomes.
- `appworld_apps_bundle_inventory_result_freeze.schema.json`: closed successful
  hash-only bundle inventory and static-protocol-design gate.
- `appworld_in_memory_static_api_inventory_protocol_validation.schema.json`:
  closed no-real-decryption design-validation result.
- `planbench_xl_capacity_audit_design.schema.json`: closed no-source/no-model
  design-validation result before any external inventory.
- `planbench_xl_source_qualification.schema.json`: frozen source hashes,
  inventory, structural continuation pool, effect coverage, and stop result.
- `tau3_execution_state_continuation_screen.schema.json`: balanced 12-pair
  scripted progress-handoff result and no-model authorization boundary.
