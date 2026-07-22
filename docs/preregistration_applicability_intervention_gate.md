# Applicability intervention gate: frozen development protocol

## Status

This protocol is frozen before implementation or fitting of the intervention
gate. It follows the stopped conservative rule-reranking experiment and is exploratory development
work, not confirmatory evidence. No Recovery Validity, Safety Violation, model
action, or sealed validation outcome may be read.

The previous v1 and v2 selectors remain immutable. This experiment does not
constitute PROPER v3 and may not be evaluated by reusing their model outcomes.

## Question

Can public target structure and public Top-10 candidate structure predict when
TF-IDF Rank-1 is environment-inapplicable and an applicable Top-10 replacement
exists, while rarely changing an already-applicable Rank-1?

The label measures an applicability opportunity only. It does not establish
that exposing the replacement improves model Recovery Validity.

## Inputs and features

Features are extracted before evaluator labels are joined. They include the
normalized target failure state, error code, tool, field/path structure and
retry count. For each candidate in original TF-IDF order they include parsed
policy, public source failure state and tool, repair targets, target/source tool
agreement, public compatibility, and enabled contradiction count. Aggregate
policy and compatibility counts are included.

IDs, provenance, fault metadata, recoverability, environment labels, outcomes,
raw argument values, instruction text, TF-IDF scores, and experience IDs are
excluded. Mutation of evaluator-only labels must not change a feature vector.

## Frozen model and cross-validation

Use a sparse dictionary vectorizer and L1 logistic regression with `C=0.25`,
balanced class weights, `liblinear`, maximum 2000 iterations, and random seed
20260721. Use deterministic shuffled five-fold stratified cross-validation with
the same seed. Every target receives exactly one out-of-fold probability.

The intervention threshold is fixed at 0.75. It may not be selected or adjusted
from cross-validation results. A negative or lower-confidence prediction keeps
TF-IDF Rank-1. A positive prediction uses the already frozen PROPER v1
deterministic selection; no new candidate-scoring rule is introduced.

## Frozen development gates

All conditions must pass:

- exact preservation of at least 95% of 228 Rank-1-applicable targets;
- an applicable selected candidate on at least 30% of all 104 Rank-1-
  inapplicable conflicts;
- recall of at least 35% on the 96 positive intervention-available labels;
- intervention precision of at least 70%;
- exactly one out-of-fold prediction per target.

Failure stops this direction without changing features, regularization,
threshold, or folds. Passing permits one final fit on all 332 development
targets and serialization of its public vocabulary and coefficients. It does
not authorize a model-outcome experiment. Any use of unused benchmark data or
Qwen requires a new preregistration after review.
