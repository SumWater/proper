# PROPER v2 archival commit plan

No file is staged and no commit has been created. This plan separates evidence
that existed before each method extension.

## Commit A: unified v2 and frozen v2.1 archive

Include the base PROPER v2 contracts, selector, compatibility and extraction
source; timeout and ToolSandbox feasibility/preparation/capacity code; v2.1
model-pilot code, configs, schemas, tests, protocols, and result report.

Force-add only these ignored structured output directories:

- `outputs/proper_v2/timeout_capacity_v2/`
- `outputs/proper_v2/timeout_pair_v2/`
- `outputs/proper_v2/toolsandbox_action_memory_preparation/`
- `outputs/proper_v2/toolsandbox_dynamic_pilot/`
- `outputs/proper_v2/toolsandbox_feasibility/`
- `outputs/proper_v2/toolsandbox_scripted_smoke/`
- `outputs/proper_v2/toolsandbox_selector_capacity/`
- `outputs/proper_v2/toolsandbox_selector_capacity_v2/`
- `outputs/proper_v2/toolsandbox_selector_capacity_v2_1/`
- `outputs/proper_v2/toolsandbox_model_pilot_v2_1/`

The stale standalone `runner_validation.json` must remain byte-for-byte and be
committed together with `v2_1_freeze_audit.md`, which explains why it is not
the later same-process passing validation.

Exclude every `v2_2` or `v2_2_1` implementation and result from this commit.

## Commit B: frozen v2.2 lifecycle development

Include:

- `src/failure_memory/proper_v2/v2_2/`;
- the v2.2 lifecycle, held-out audit, unconsumed-capacity, and Qwen lifecycle
  configs, schemas, experiments, tests, protocols, stage index, and result
  report;
- the ignored structured outputs under:
  - `toolsandbox_heldout_target_audit_v2_2/`;
  - `toolsandbox_lifecycle_development_v2_2/`;
  - `toolsandbox_qwen_lifecycle_development_v2_2/`;
  - `toolsandbox_unconsumed_capacity_v2_2/`.

This commit records the 12-pair Qwen run as development-only and retains the
0/9 post-failure completion limitation.

## Commit C: frozen v2.2.1 continuation development

Include the versioned continuation source, schema, configs, tests, protocols,
four-condition preparation, prospective target inventory, scripted
ToolSandbox validator, Qwen development runner, single remote entry point,
stage documentation, and the audited development result report.

Force-add only these ignored structured output directories:

- `outputs/proper_v2/toolsandbox_continuation_development_v2_2_1/`
  (prepared manifest and static validation; no standalone dynamic artifact was
  produced by the frozen entry);
- `outputs/proper_v2/toolsandbox_continuation_target_inventory_v2_2_1/`;
- `outputs/proper_v2/toolsandbox_qwen_continuation_development_v2_2_1/`.

This commit records the 12-pair Qwen run as development-only, retains the 0/9
post-failure completion and later-action repetition limitations, and records
that the prospective inventory yielded zero eligible targets.

## Global exclusions

Never stage:

- `proper_v2_remote_overlay.zip`;
- `__pycache__/`, `.pyc`, test caches, or temporary files;
- console logs or redirected `tee` output;
- unrelated user changes.

Because `outputs/proper_v2/*` is ignored, every forced add must name an exact
approved result directory. A broad `git add -f outputs/proper_v2` is not
allowed.
