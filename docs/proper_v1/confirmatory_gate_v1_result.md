# Confirmatory Gate v1 result

## Confirmatory decision

`SUPPORT_PRIMARY_HYPOTHESIS`

The frozen conservative argument-repair gate improved Qwen3-8B Recovery
Validity relative to TF-IDF Rank-1 on the preregistered gate-changed public-test
population. The method, test cohort, threshold, memory bank, model and endpoint
were fixed before model outputs were generated.

The immutable raw result file has SHA256
`6e44ef0eba2bf7efeed7163d61a621d2a1a5385b6aa507f7ce0417222d2fceb8`.
There were no model-output parse failures.

## Primary comparison

The primary population contains 115 of 189 valid argument-omission targets for
which the frozen gate changed TF-IDF Rank-1 before inference.

| Metric | TF-IDF Rank-1 | PROPER Gate |
|---|---:|---:|
| Recovery Validity | 99/115 (86.09%) | 109/115 (94.78%) |
| Task Completion | 99/115 (86.09%) | 109/115 (94.78%) |
| Safety Violations | 0 | 0 |
| Repeated Invalid Calls | 0 | 0 |

Paired results:

- positive transfers: 10;
- negative transfers: 0;
- paired risk difference: +8.70 percentage points;
- 95% CI: [+3.52, +13.87] percentage points;
- exact two-sided McNemar p = 0.001953;
- memory-induced action changes: 13;
- inapplicable-memory harms: 0.

The preregistered criterion, PPT greater than PNT with p below 0.05, is met.

## All valid targets and controls

These estimates are descriptive because the primary population was frozen as
the gate-changed subset.

| Condition | Recovery Validity | Repeated Invalid Calls | Safety Violations |
|---|---:|---:|---:|
| No Memory | 156/189 (82.54%) | 5 | 0 |
| TF-IDF Rank-1 | 162/189 (85.71%) | 2 | 0 |
| PROPER Gate | 172/189 (91.01%) | 2 | 0 |
| Matched Applicable | 172/189 (91.01%) | 2 | 0 |

Across all 189 valid targets, Gate versus Rank-1 also has 10 positive and zero
negative transfers, a descriptive +5.29 percentage-point difference.

The applicability gate changed an inapplicable Rank-1 to an evaluator-
applicable memory on all 115 primary targets. It retained an applicable Rank-1
on 59 targets and retained an inapplicable Rank-1 on 15 targets.

## Tool-stratified result

| Tool | N | Rank-1 RV | Gate RV | PPT | PNT | Action changes |
|---|---:|---:|---:|---:|---:|---:|
| close_account | 12 | 12 | 12 | 0 | 0 | 0 |
| get_doc | 25 | 9 | 19 | 10 | 0 | 13 |
| read_file | 16 | 16 | 16 | 0 | 0 | 0 |
| search_docs | 8 | 8 | 8 | 0 | 0 | 0 |
| update_account | 11 | 11 | 11 | 0 | 0 | 0 |
| validate_cron | 21 | 21 | 21 | 0 | 0 | 0 |
| write_file | 22 | 22 | 22 | 0 | 0 | 0 |

All 10 improvements and all 13 action changes occur on `get_doc`. All 10
improvements expose the same dev memory,
`experience::dev_v2_retrieval_clean_medium_relaxed_00707::argument_omission_extension`.
The other six tools had perfect Rank-1 Recovery Validity in the primary
population, leaving no observed improvement opportunity.

## Valid claim and limitation

The defensible claim is narrow:

> On held-out public-test base tasks converted into deterministic
> argument-omission conditions, a frozen applicability gate selecting dev-
> sourced repair memories improved Qwen3-8B Recovery Validity over TF-IDF
> Rank-1 without observed negative transfer.

The argument-omission condition is a disclosed local extension, not the
released public-test fault plan. The causal Recovery Validity gain is
concentrated in one tool and one selected memory. Therefore this experiment
does not establish universal failure-memory selection, authorization/timeout
handling, or cross-tool causal improvement.

No threshold, feature, memory or subgroup may be retuned on these test results.
Any broader claim requires a new dataset or independently held-out evaluation.
