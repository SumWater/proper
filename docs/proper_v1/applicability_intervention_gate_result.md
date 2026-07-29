# Applicability intervention gate: frozen development result

## Status

`PASS_APPLICABILITY_INTERVENTION_GATE`

The configuration, feature extractor, and evaluation runner were hashed before
the one-time cross-validation run. The fixed probability threshold was 0.75.
No threshold, feature, fold, or model hyperparameter was changed after seeing
the results. No language model or recovery outcome was loaded, and sealed
validation model outcomes remain unread.

Locked method identities:

- configuration:
  `58e81038ae445c4c99ee822d5e6ca9dbd226e9df0ccef98df34fc2cd279ee25e`;
- feature source:
  `d8f228ec51acd5672c2704c6fd1da4eabd391c41e9d0c1e7aa0b90b7ee0e1bee`;
- evaluation runner:
  `3c3225438b14d1795e28b0628d4b871ae50e8d8ab33cfe03cd90a45cb0d120f1`;
- fitted model payload:
  `c1d068b602e4f6757f4dfb9d93eed8e03b860e433494c296de0dcb32f18954a9`;
- complete result file:
  `074f2ff97a917baf087a69b940a49c3a1668a8fe82ea99b5f9365db208b5736d`.

## Frozen-gate results

| Metric | Result | Frozen gate |
|---|---:|---:|
| OOF true positives | 59 | — |
| OOF false positives | 1 | — |
| OOF false negatives | 37 | — |
| OOF true negatives | 235 | — |
| Intervention precision | 98.33% | at least 70% |
| Positive-label recall | 61.46% | at least 35% |
| Exact preservation of applicable Rank-1 | 228/228 (100%) | at least 95% |
| Applicable selection among 104 conflicts | 56/104 (53.85%) | at least 30% |
| Every target predicted exactly once | yes | required |

All frozen gates passed. The protocol therefore fitted one final L1 logistic
model on all 332 development targets. It has 343 vectorized features and 21
nonzero coefficients. The complete coefficient list is stored in the result
artifact. The completed Windows CPU run used Python 3.12.7, NumPy 1.26.4,
SciPy 1.13.1, and scikit-learn 1.5.1; these are recorded separately so the
older model-experiment requirements lock remains unchanged.

## Scope limitation

All 59 OOF true positives are `argument_omission_extension` instances. They
span seven tools, so the result is not a single-tool artifact, but the gate
identified no authorization or timeout intervention opportunity. The sole
false positive is a persistent-authorization instance and did not change the
selected memory because frozen PROPER v1 kept Rank-1 there.

Consequently, this result supports only a narrow claim: public target and
candidate structure can conservatively identify many missing-argument cases
where deterministic reranking finds an applicable memory. It does not validate
a general failure-applicability classifier and does not demonstrate Recovery
Validity improvement.

## Decision

The development gate is retained as a viable component, but no GPU or
model-outcome experiment is authorized by this result. Before using unused
data, a new preregistration must:

- name the method as a conservative schema/argument-repair gate rather than a
  universal applicability gate, unless new development evidence covers other
  failure classes;
- make Recovery Validity the primary outcome;
- compare the frozen gate against TF-IDF Rank-1 on genuinely unused targets;
- report authorization and timeout strata separately, including zero coverage;
- retain No Memory and Matched Applicable controls where feasible;
- forbid any refit or threshold adjustment on the unused evaluation split.
