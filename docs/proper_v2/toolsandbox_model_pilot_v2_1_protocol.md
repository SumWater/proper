# ToolSandbox phase-aware model pilot protocol

This protocol freezes the exploratory Qwen3-8B pilot that follows the
PROPER v2.1 phase-aware capacity audit. It does not authorize a confirmatory
claim or a GPU run by itself.

## Frozen cohort

The primary cohort contains exactly the 12 capacity records for which the
TF-IDF Rank-1 card and the PROPER v2.1 card prescribe behaviorally distinct
interventions:

- 9 `post_failure` prerequisite-recovery pairs;
- 3 `pre_action` safe-stop pairs.

The other seven records are identity-only memory changes. They are excluded
from the primary effect estimate and retained only as a secondary preservation
cohort.

## Paired conditions

Every target is branched from an identical ToolSandbox context. The fixed
condition order is:

1. `tfidf_rank1_memory`;
2. `proper_v2_1_memory`.

The user instruction, decision phase, proposed or failed action, visible
evidence, available tool schemas, seed, decoding configuration, and action
budget are identical within a pair. Only the retrieved memory card changes.
The memory is supplied on every decision in the bounded recovery continuation.

For `post_failure`, both branches start after the same required failing tool
call. Frozen scripted prelude actions establish any already-resolved entity or
temporal state before that call, and the required exception text is checked.
For `pre_action`, both branches start before the potentially unsafe or
underspecified action; no artificial failure is introduced.

## Model and execution budget

The local Qwen3-8B worker uses greedy decoding with thinking disabled,
`max_new_tokens=256`, and seed `20260730`. Each branch has at most four model
decisions and four tool calls after the branch point. Tool exceptions are
returned as visible observations while budget remains. Invalid model output
terminates the branch with reason `invalid_model_output`.

## Evaluation and interpretation

ToolSandbox final similarity is the primary exploratory endpoint. Results must
also report milestone similarity, minefield similarity, first-decision policy
alignment, invalid output, tool exceptions, repeated identical calls, and
cost. Results are stratified by `pre_action` and `post_failure`; a pooled value
may be descriptive only.

This small, capacity-selected pilot can show whether the unified selector
creates useful behavioral differences in an external stateful benchmark. It
cannot establish applicability to all Agent-memory settings or support a
confirmatory generalization claim.
