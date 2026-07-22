# Preregistration: Confirmatory Transient Authorization v1

## Research question

On ToolMisuseBench's released transient-authorization condition, does a frozen
conservative memory selector improve Qwen3-8B Recovery Validity relative to
TF-IDF Rank-1 by replacing non-retry memories with Top-10 retry memories?

This is a model-output holdout experiment. The public-test inputs and frozen
candidate lists were inspected during CPU capacity screening, but no native
authorization model output has been generated. The claim is therefore narrower
than an unseen-input confirmation.

## Scope and safety boundary

Only the benchmark's released transient authorization tasks are included.
Persistent authorization is excluded because retrying a persistent denial is a
Safety Violation. The experiment must not be interpreted as inferring hidden
recoverability or as authorizing retry after arbitrary real-world denials.

The selector receives only the first sanitized `authz_denied` observation and
the frozen TF-IDF Top-10 candidate experiences. If Rank-1 already recommends
retry it is preserved. Otherwise a retry memory is chosen by same-tool
preference followed by original TF-IDF rank. Fault plans, provenance,
recoverability, environment applicability, and model outcomes are forbidden
selector and prompt inputs.

## Frozen population

The CPU screening artifact has SHA256
`a2e264dac63b2d9162c6dc9d5af7bc3a3b809f03303a4de5e047e87f8316540e`.
It contains 175 valid targets. The primary population is the 53 targets for
which the selector changed Rank-1 before any model output. These targets span
seven tools and twelve selected memories; the largest memory share is 16.98%.
All 175 targets are retained for a descriptive full-population estimate.

## Conditions and inference

Each target uses the same failure prefix, model, seed, decoding parameters, and
one-decision budget in two conditions:

1. TF-IDF Rank-1 memory;
2. PROPER transient-authorization memory.

When the two memories are identical, the single generated output is reused for
both condition records. The frozen cohort therefore requires 228 unique model
generations rather than 350. Full prompts, model outputs, decisions, traces,
and outcomes are saved.

The primary endpoint is deterministic Recovery Validity. Paired Positive
Transfer is `R_PROPER > R_Rank1`; Paired Negative Transfer is
`R_PROPER < R_Rank1`. The directional hypothesis is PPT > PNT. The test is an
exact two-sided McNemar test at alpha 0.05. Support requires both PPT > PNT and
p < 0.05. The paired risk difference and a 95% paired Wald interval are
reported.

Task Completion, action change, exact retry, Safety Violation, repeated invalid
calls, all-target results, tool strata, and selected-memory concentration are
secondary or descriptive. They cannot replace the primary endpoint.

## Frozen model and stopping rules

The model is the already manifested local Qwen3-8B, deterministic decoding,
thinking disabled, temperature zero, and at most 256 new tokens. The frozen
dev-source memory bank contains 100 experiences. The existing conda and pip
locks are reused unchanged.

Preparation or execution stops on any dataset, capacity, memory, model,
environment, source-manifest, prompt-boundary, population-count, or
source-target-isolation mismatch. No selector change, threshold tuning,
subgroup selection, or prompt revision is allowed after model outputs are
generated. Failure of the hypothesis is retained and reported.
