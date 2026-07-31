# PROPER v2.3 schemas

This directory is reserved for the action-effect, execution-ledger, controller
decision, and version-specific result schemas. Frozen schemas under
`schemas/proper_v2/` remain read-only.

- `action_execution_ledger.schema.json`: complete-trajectory proposed,
  executed, succeeded, failed, and outcome-unknown records.
- `controller_decision.schema.json`: unified allow/verify/replan/stop decision
  and independent remaining budgets.
