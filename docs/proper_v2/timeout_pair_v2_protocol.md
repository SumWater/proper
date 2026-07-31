# PROPER v2 timeout paired protocol

## Status

This protocol is defined after the CPU-only capacity screen and before any
timeout-cohort model output is generated. The capacity screen selected the
model-output holdout population; it is not evidence of recovery effectiveness.

GPU execution remains unauthorized until deterministic preparation artifacts,
source hashes, environment hashes, and model hashes are locked.

## Population

The descriptive population contains the 177 valid released native-timeout
targets recorded by the frozen capacity artifact. All 364 base task IDs used
by the earlier argument-omission and transient-authorization experiments were
excluded before selection.

The primary population is fixed to the 32 targets for which unified PROPER v2
changed TF-IDF Rank-1 before model outputs existed. It covers seven target
tools and six selected memories; the largest selected-memory share is 0.375.

The public-test inputs have been inspected for capacity and deterministic
prompt construction. They are model-output holdout data, not unseen-input
holdout data.

## Conditions

Each target starts from exactly the same observable failure prefix. The two
conditions differ only in the injected retrieved experience:

1. `tfidf_rank1_memory`;
2. `proper_v2_memory`.

Condition order, Qwen3-8B decoding, maximum output length, parser, environment,
and one-decision recovery horizon are fixed. Identical prompts on unchanged
targets are executed once and reused.

## Primary endpoint and decision

The primary endpoint is paired Recovery Validity on the 32 selector-changed
targets. Let PPT count pairs where PROPER v2 succeeds and Rank-1 fails, and PNT
count pairs where PROPER v2 fails and Rank-1 succeeds.

The directional claim is supported only when:

- PPT is greater than PNT; and
- the exact two-sided McNemar p-value is below 0.05.

The experiment also reports the paired risk difference and 95% confidence
interval. No threshold, selector rule, cohort, prompt, or endpoint may be
changed after model outputs are observed.

## Secondary reporting

Secondary descriptive results include task completion, exact retry,
memory-induced action change, safety violations, repeated invalid calls,
all-target outcomes, target-tool strata, Rank-1 operation-transition strata,
and selected-memory concentration.

The timeout experiment extends evidence across failure type but remains a
one-step retry setting. Even a positive result does not establish applicability
to all Agent memory scenarios or to prerequisite, fallback, switch-tool,
verification, or ask-user policies.

