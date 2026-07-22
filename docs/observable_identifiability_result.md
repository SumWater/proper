# Exploratory observable-identifiability audit

## Scope

This audit was performed after the conservative rule reranker stopped. It is exploratory development
analysis, not a preregistered result and not evidence of model utility. It uses
the 332 development targets and evaluator applicability labels only after
constructing signatures from allowed public features. It loads no model, reads
no model output, and leaves the 52 validation model outcomes sealed.

The target label is whether TF-IDF Rank-1 is inapplicable while at least one
Top-10 candidate is applicable. It therefore measures whether an applicability
intervention is available, not whether a changed memory will improve Recovery
Validity.

## Results

| Observable feature family | Ambiguous targets | In-sample deterministic majority ceiling |
|---|---:|---:|
| Failure state + Rank-1 policy | 188 | 244/332 (73.49%) |
| State + tool + Rank-1 policy | 181 | 260/332 (78.31%) |
| Normalized target structure + Rank-1 policy | 64 | 309/332 (93.07%) |
| Target structure + Top-10 policy counts | 32 | 319/332 (96.08%) |
| Target structure + ordered Top-10 public profiles | 21 | 323/332 (97.29%) |

Always keeping TF-IDF Rank-1 is correct for this label on 236/332 (71.08%).
The population contains 228 Rank-1-applicable targets, 96 Rank-1-inapplicable
targets with an applicable Top-10 replacement, and eight without one.

## Interpretation

The v2 target-only trigger was too coarse. Candidate-set composition contains
additional public signal and raises the descriptive ceiling above the old 95%
preservation target. However, the richest signature creates 214 groups from
only 332 targets. Its 97.29% number is an in-sample majority bound and may
reflect sparse benchmark-specific patterns; it is not a validated classifier
result.

Twenty-one targets remain observably ambiguous even with ordered candidate
profiles. Most unresolved groups concern first authorization denial, where
public observations do not reveal persistence. No method should infer transient
versus persistent authorization from hidden recoverability.

## Next method decision

Do not revive or hand-tune another rule reranker on the existing model
outcomes. The next defensible method is a separately named, transparent
**applicability intervention gate**:

1. represent the target's normalized public failure structure;
2. represent the ordered Top-10 candidates by public policy, source failure,
   source tool, repair target, and rank;
3. predict only `keep Rank-1` versus `allow deterministic reranking`;
4. retain the frozen v1 compatibility ranking after an intervention;
5. default to keeping Rank-1 under uncertainty.

Before implementation, freeze grouped cross-validation, a maximum false
intervention rate on Rank-1-applicable targets, minimum recall on the 96
available interventions, feature vocabulary, and model complexity. This stage
may use all 332 targets as development data but no recovery outcomes. Only a
frozen gate that passes development cross-validation may proceed to a new
experiment on genuinely unused targets. Qwen scoring and LoRA remain
unjustified at this point.
