# PROPER v2.1 pre-v2.2 freeze audit

## Git state

At audit time, branch `proper_v2` matched `origin/proper_v2` at `6eeb75d`.
The unified v2/v2.1 method, configs, schemas, experiments, tests, and selected
results had not yet been committed. Three directory README files were
modified; the remaining method files were untracked. Generated
`outputs/proper_v2/*` and most `work/*` logs were excluded by `.gitignore`.

No v2.2 implementation file existed before this audit.

## Recomputed v2.1 evidence

Independent recomputation from
`outputs/proper_v2/toolsandbox_model_pilot_v2_1/qwen_results.json` confirmed:

- 12 pairs and 24 conditions;
- 87 of 87 raw model responses parse as the recorded valid JSON decisions;
- 12 of 12 paired starts are identical;
- `pre_action`: TF-IDF mean 0.0, PROPER mean 1.0, 3/0/0
  better/worse/tied;
- `post_failure`: both means 0.4296296296, 0/0/9
  better/worse/tied;
- PROPER first-step alignment 3/3 pre-action and 9/9 post-failure;
- TF-IDF first-step alignment 0/3 pre-action and 7/9 post-failure;
- pre-action minefields 3/3 for TF-IDF and 0/3 for PROPER;
- post-failure exceptions 9 versus 24 and consecutive repeated calls 8 versus
  21 for TF-IDF versus PROPER.

These data support a selector first-step effect and expose a lifecycle
failure. They do not show improved post-failure final completion or cost.

The result SHA256 is
`3ec804cb5d8e0ba98e60d36099a525210965b6fcfe1ddf9426549b938bc3f07a`.
The historical Qwen log was separately checked during the audit, but it is
not required for the frozen commit. The structured `qwen_results.json`
contains the request identities and recorded decisions needed for analysis.

## Standalone runner-validation discrepancy

The standalone
`outputs/proper_v2/toolsandbox_model_pilot_v2_1/runner_validation.json`
is an earlier artifact:

- `runner_validation_passed` is false;
- its stored config identity is
  `ea8490aa507fc1c1439d1f5c7b58b07e14b8d88aff712b7eb7252ef06d57f287`;
- the current frozen runner config identity is
  `c393dd88ab19cb32e7509fe94fdd7c7c7ff9a33ee0777517af754ab7d08de37e`.

It must not be described as the final passing validation or silently
overwritten. The Qwen result embeds the later same-process scripted validation
with `runner_validation_passed=true`; the Qwen config freezes the matching
runner config and source hashes.

## Freeze recommendation

Before committing v2.2, create a pre-v2.2 archival commit on `proper_v2`
containing:

- all hand-authored v2/v2.1 source, configs, schemas, protocols, tests, and
  README changes;
- the curated ToolSandbox preparation/capacity/model-pilot outputs needed by
  the recorded hash chain;
- this audit note.

Keep the historical standalone runner-validation file byte-for-byte and retain
the discrepancy note. Exclude `proper_v2_remote_overlay.zip`, Python caches,
and all console logs. Do not create the commit without an explicit staging
review.
