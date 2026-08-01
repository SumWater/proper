# PROPER v2.3 five-condition preparation remote handoff

## Infrastructure correction

Remote preparation attempt at project revision `956bee5` generated its
`prepared_manifest.json` and then stopped before tests because preparation
schema v1 incorrectly required `branch_prefix_recipe` to be an object. The
frozen source contains three legitimate `pre_action` records where that field
is null. No model, GPU, or target scenario was executed.

The failed manifest must remain at
`outputs/proper_v2_3/five_condition_development/prepared_manifest.json` and
must not be edited or overwritten. Validation protocol v2 requires that file
to exist and records its SHA-256 in the new envelope.

Schema v2 changes only two infrastructure properties:

- `branch_prefix_recipe` accepts `object` or `null`, matching the immutable
  source manifest;
- every later preparation uses a UTC/host/revision-qualified output directory
  under `outputs/proper_v2_3/five_condition_development_remote/`.

The five conditions, method, prompts, action-effect contracts, budgets,
endpoints, exclusions, model settings, and stop rules are unchanged. This is
an infrastructure correction before any model output, not protocol tuning.

Only a protocol-v2 envelope with 72 passing tests may advance to the separate
model-runner implementation gate. It still authorizes no model or GPU run.
