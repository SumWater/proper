# Confirmatory Gate v1 preregistration

## Status and claim boundary

This protocol is frozen before acquisition or inspection of the public-test
task file and before any public-test model output. The method is a conservative
argument-repair memory selector, not a universal failure-memory selector.

All 900 dev tasks, the 332 previous development targets, and every prior Qwen
output are development data. They cannot support the result of this experiment.
The fixed 100-memory bank and fitted gate come from dev; every target comes from
the immutable public-test split.

## Immutable data

Use ToolMisuseBench v0.2 large at revision
`98eb28718b0393e029088ce80604c48807216de4`. The public-test file must contain
1,695,141 bytes and have SHA256
`12c5e1e93926f4089dfc8d0c60cea53b556057360562375510744858fc6f1161`.
Any mismatch stops the experiment.

Only released clean public-test base tasks are eligible. For each, construct
the deterministic local argument-omission extension already used in
development: remove one required field from the correct initial action and
replay the resulting public `missing_required_arg` failure. Use every valid
base task, ordered by the frozen hash seed. This extension must be labeled
explicitly as a local evaluation condition rather than a released fault.

## Frozen method

Retrieve Top-10 from the unchanged 100-source dev memory bank. Build only the
public target/candidate features used by the fitted gate. Score them using the
frozen nonzero logistic coefficients and threshold 0.75. A lower score keeps
TF-IDF Rank-1; a positive gate uses the immutable PROPER v1 deterministic
ranking. Test applicability labels, fault metadata, IDs, recoverability and
model outcomes are forbidden method inputs.

No feature, coefficient, threshold, memory source, retrieval configuration or
candidate rule may be changed after test acquisition. If fewer than 50 targets
have a gate-selected memory different from Rank-1, stop without a GPU run.

## Conditions and primary population

For every valid target prepare complete prompts for No Memory, TF-IDF Rank-1,
PROPER Gate and the highest-TF-IDF environment-applicable dev memory. Identical
Rank-1 and Gate prompts may reuse one deterministic model output but must retain
both condition records and the shared-output identity.

The primary population is all targets for which the frozen gate changes the
selected memory before any model output is generated. This population rule is
deployable and outcome-blind. The primary contrast is PROPER Gate versus
TF-IDF Rank-1. No Memory and Matched Applicable are descriptive controls. All
valid targets remain in the artifact for an ecological secondary estimate.

## Endpoint and decision

The primary endpoint is deterministic Recovery Validity. For each primary pair
define PPT when Gate succeeds and Rank-1 fails, and PNT when Gate fails and
Rank-1 succeeds. Test discordant counts using exact two-sided McNemar at
alpha 0.05 and report paired risk difference with the frozen 95% interval.

The hypothesis is supported only when PPT is greater than PNT and the exact
two-sided p-value is below 0.05. Task Completion, action change, Safety
Violation, Repeated Invalid Calls and recovery costs remain separate secondary
outcomes. Failure of the primary test is reported as failure; no subgroup,
threshold or feature revision may replace it.

## Model and execution freeze

Use the already hashed local Qwen3-8B, greedy decoding, thinking disabled,
maximum 256 new tokens and one post-failure decision. Save every prompt, raw
model output, parsed decision, trace, condition outcome, environment lock,
source manifest and hash. Preparation and a synthetic CPU dry-run must pass
before any GPU run.
