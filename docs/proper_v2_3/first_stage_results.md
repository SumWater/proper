# PROPER v2.3 first-stage local validation result

## Status

`PASS_FIRST_STAGE_LOCAL_VALIDATION`

The first execution-aware lifecycle stage completed locally without a model,
GPU, external API, or target-scenario play-through.

- structured result:
  `outputs/proper_v2_3/first_stage_validation/results.json`;
- result SHA-256:
  `7d17a69032e6f4fab8293b837ba8dd61484f2726ecf317a71d158c677d227056`;
- result bytes: 40,765;
- v2.3 unit and scripted-wrapper tests: 44 passed, 0 failed, 0 errors,
  0 skipped;
- scripted multi-step traces: 5/5 passed;
- recorded first-stage source hashes: 23.

## Scripted coverage

The dependency-light traces cover:

1. pre-action safe stop before a side effect;
2. successful prerequisite consumption and ordinary-planning handoff;
3. successful duplicate message proposal blocked after one execution;
4. unknown side-effect outcome routed to bounded read-only verification;
5. successful idempotent state-setting repeat blocked.

Unit tests additionally cover:

- deterministic normalized action identity;
- proposed/executed/succeeded/failed/outcome-unknown ledger transitions;
- strict blocked-proposal non-execution;
- success/trigger conflict;
- unknown effect and missing-verification fail-closed behavior;
- retry, verification, invalid-decision, and replan budget independence and
  exhaustion;
- stable action-effect contracts with observable strengthening of previously
  unknown retry safety;
- successful verifier-action deduplication;
- explicit success-evidence violation precedence over trigger clearance;
- recursive rejection of scenario, semantic-family, gold-action, evaluator,
  and prior-model-result inputs;
- both `pre_action` and `post_failure` selection adapters;
- frozen v1/v2 structured-result hashes.

These are scripted controller tests, not model behavior or task-completion
evidence.

## Frozen regression

The validation rechecked the two PROPER v1 confirmatory result hashes and the
seven v2.1/v2.2/v2.2.1 identities named in `START_HERE.md`. All matched.
Existing v2 regressions also passed after the optional schema validator was
supplied from a temporary validation directory.
The combined `test_proper_v2*.py` suite passed 97/97 and the combined
`test_toolsandbox*2*.py` suite passed 34/34.

Draft 2020-12 schema validation used `jsonschema 4.17.3`. The repository's
declared development version remains 4.23.0; that exact version could not be
installed in the current Python 3.12 environment because the available package
index did not provide its required `rpds-py` distribution. This is an
environment-lock difference, not a schema-validation failure, and remains
explicit in the structured result.

## Target capacity

The prospective audit design validates the frozen 1,032-scenario,
zero-candidate inventory and records:

- `new_target_capacity_available=false`;
- `development_model_run_authorized=false`;
- `confirmatory_run_authorized=false`;
- disposition: `stop_no_target_capacity`.

No new source has been registered, so this stage does not proceed to a model
runner.

## Interpretation

This result establishes local consistency of the v2.3 contract, complete
action ledger, controller state machine, budgets, and scripted safety
regressions. It does not establish selector improvement, autonomous recovery
continuation, final task completion, model safety, or applicability to all
Agent-memory settings.
