# Full paper outline

## Abstract

- Problem: similarity-ranked failure memories may be applicable, inert, or harmful after a tool failure.
- Method: observable-only conservative selection over retrieved candidates.
- Evidence: two models, three failure strata, 541 targets, 403-target primary changed-selection union.
- Primary effects: bounded paired improvements over TF-IDF and strong baselines.
- Essential caveat: memory remains worse than No Memory overall for Mistral; zero/weak strata and V1 limitation.

## 1 Introduction

1. Failure recovery makes memory applicability conditional on the current public execution state.
2. Retrieval similarity and policy applicability are distinct.
3. Research question and observable-evidence constraint.
4. Summary of method and three contributions.
5. Evidence-bounded headline with negative results.

## 2 Related Work

1. Memory and experience reuse for LLM agents.
2. Retrieval/reranking and applicability estimation.
3. Tool-use failure recovery and execution feedback.
4. Selective prediction, abstention, and conservative decision rules.
5. Positioning: one-step failure-memory selection, not general agent memory or a multi-step planner.

## 3 Problem Formulation

1. Observable failure state.
2. Source-isolated memory bank and ranked candidates.
3. Keep Rank-1, select an alternative, or abstain while preserving Rank-1.
4. Recovery Validity and paired evaluation.
5. Threat boundary: hidden labels, scenario names, gold actions, and prior outcomes are forbidden inputs.

## 4 PROPER

1. Candidate policy-card representation.
2. Applicability evidence: trigger overlap and operation-specific support.
3. Preconditions, repair-target agreement, and tool compatibility.
4. Contradiction detection and observable retry safety.
5. Candidate ordering.
6. Conservative replacement gate and abstention semantics.
7. Ablations: no-gate and no-contradiction.
8. Complexity and implementation determinism.

## 5 Experimental Setup

1. Benchmark, 100-memory bank, 541 targets, and three strata.
2. Qwen3-8B and Mistral-7B-Instruct-v0.3 identities.
3. Conditions: No Memory, TF-IDF, Dense, LLM Judge, PROPER, two ablations, descriptive Oracle.
4. Frozen changed-target union (403) and all-valid sensitivity (541).
5. Deterministic generation, prompt caching, strict parsing, one-step environment reset.
6. Recovery Validity and secondary risk metrics.
7. Paired bootstrap, exact McNemar, and Holm families.
8. V1 blinded audit status and `TODO-V1`.

## 6 Main Results

1. Absolute condition results by model.
2. Primary PROPER-vs-TF-IDF paired results.
3. Dense and LLM-Judge comparisons.
4. Cross-model interpretation: relative selector improvement versus absolute memory utility.
5. Stratum heterogeneity and zero results.

## 7 Mechanism and Risk Analysis

1. Offline applicability corrections/new errors.
2. Gate ablation and intervention subset.
3. Contradiction ablation: cross-model direction conflict.
4. Positive/negative transfer relative to No Memory.
5. Repeated-invalid and parse regressions; zero observed safety events.
6. Selection-to-behavior gap.

## 8 Concentration and Robustness

1. Tool, task-domain, failure-stratum, and selected-memory concentration.
2. Qwen `get_doc`/M058 concentration.
3. Mistral dispersion and dominant scheduling group.
4. Leave-one-group-out exclusion sensitivity and its non-retraining interpretation.

## 9 Limitations and Threats to Validity

1. One benchmark, one memory bank, two 7B/8B models, one-step horizon.
2. Changed-target primary population and all-valid sensitivity distinction.
3. Automated evaluator pending V1 human validation.
4. Mistral memory-vs-No-Memory negative result.
5. Contradiction component not independently validated.
6. Zero safety events do not establish safety.
7. Descriptive subgroup/concentration analyses do not establish causal mechanisms.
8. No E6/Tau3 or external-generalization evidence.

## 10 Conclusion

- Conservative applicability-aware selection can improve over direct retrieval in the evaluated setting.
- Model and failure context determine whether memory is useful at all.
- Honest recovery-memory evaluation must include No Memory, negative transfer, zero cells, and concentration diagnostics.

## Appendices

- Full all-valid and stratum tables.
- Prompt/selector schemas and forbidden-input boundary.
- Exact statistical procedure and seeds.
- Source/result hashes and reproduction commands.
- V1 protocol and final agreement report when complete.

