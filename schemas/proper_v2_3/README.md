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
