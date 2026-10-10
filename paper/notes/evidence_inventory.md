# Evidence inventory (P0--E5 only)

Status: audited against frozen result locks on 2026-08-18. All rates below are paired-instance or simple empirical rates over the stated frozen population. “Formal” means the comparison belongs to a pre-frozen inferential family; “descriptive” means no new hypothesis-test claim is permitted.

## Common definitions and identities

- **Primary endpoint:** Recovery Validity, a paired binary endpoint. A parsed recovery decision must execute without a second error and complete the task; a safety violation is invalid.
- **Primary population:** 403 targets where at least one non-oracle selector in `{Dense, LLM Judge, PROPER, PROPER-no-gate, PROPER-no-contradiction}` selected a different memory identity from TF-IDF. Strata: 152 argument omission, 146 transient authorization, 105 timeout.
- **All-valid sensitivity population:** 541 targets: 189 argument omission, 175 transient authorization, 177 timeout.
- **Memory bank:** 100 source-isolated memories; TF-IDF Top-10 supplies candidates to PROPER and the LLM Judge.
- **Models:** Qwen3-8B (frozen 15-file manifest) and Mistral-7B-Instruct-v0.3 at revision `c170c708c41dac9275d15a8fff4eca08d52bab71` (frozen 11-file manifest).
- **Inference:** paired risk difference, 10,000-replicate paired-instance percentile bootstrap 95% CI, exact two-sided McNemar test, and Holm correction within pre-frozen families.
- **Formal source:** `outputs/paper_2026/e2_e3_formal_analysis/tables.json`, SHA256 `b14119e7eee348c085cb6bcbefca9e8a2ab2db8c4e283265799680acc232bf35`; result lock `configs/paper_2026/e2_e3_analysis_v1_0.result.lock.json`.

## Offline selection evidence

Source: `outputs/paper_2026/e1_selection/analysis.json`, field families `changed_counts`, `applicable_selection_counts`, `corrections_vs_tfidf`, and `new_errors_vs_tfidf`; SHA256 `5c84d3aeda8de387e840ec289c08ea7626e2e66c7d9a112fdd6fd4dcd57d6d8b`; result lock `configs/paper_2026/e1_selection_v1_0.result.lock.json`. Population: all 541 targets. These are descriptive selector-side labels, not human-validated behavioral outcomes.

| ID | Number | Metric / condition | Status | Supports | Does not support |
|---|---:|---|---|---|---|
| SEL-01 | 205/541 (37.9%) | PROPER memory identity differs from TF-IDF | descriptive | PROPER intervenes with nonzero coverage | behavioral improvement |
| SEL-02 | 513/541 (94.8%) | PROPER-selected memory is evaluator-policy-applicable | descriptive, pending V1 reliability | fewer labeled selection errors than baselines | universal applicability or causal validity |
| SEL-03 | 165 corrections, 0 new errors | PROPER vs TF-IDF policy-applicability labels | descriptive, pending V1 reliability | conservative gate can avoid label-defined new errors | perfect real-world precision |
| SEL-04 | 300 changes; 438 applicable | PROPER-no-gate | descriptive | removing gate expands intervention and reduces labeled precision | the gate always improves behavior |
| SEL-05 | 75 new errors | PROPER-no-gate vs TF-IDF applicability labels | descriptive | gate suppresses a substantial labeled-risk set | a safety-violation reduction |
| SEL-06 | 241 changes; 531 applicable | PROPER-no-contradiction | descriptive | contradiction removal changes coverage | independent behavioral benefit of contradiction checking |
| SEL-07 | Dense: 383 applicable, 79 corrections, 44 new errors | Dense vs TF-IDF | descriptive | Dense is a stronger retrieval baseline than TF-IDF on labels | end-to-end superiority |
| SEL-08 | LLM Judge: 340 applicable, 68 corrections, 76 new errors | fixed Qwen3-8B reranker | descriptive | LLM reranking is not automatically conservative | general weakness of LLM judges |

## Primary and strong-baseline behavioral evidence

Each row uses the 403-target changed-target union. Source fields: `inference_rows[*].{pair_count,baseline_successes,treatment_successes,positive_discordant,negative_discordant,paired_risk_difference,paired_bootstrap_ci,exact_two_sided_mcnemar_p,holm_adjusted_p}`.

| ID | Model / comparison | Successes | Discordance (+/−) | RD, 95% CI | Holm p | Status and allowed claim |
|---|---|---:|---:|---|---:|---|
| MAIN-01 | Qwen, PROPER vs TF-IDF | 366 vs 351 of 403 | 15/0 | +3.72 pp [1.99, 5.71] | 0.000122 | formal primary; PROPER improves Recovery Validity relative to TF-IDF for this model and population |
| MAIN-02 | Mistral, PROPER vs TF-IDF | 180 vs 158 of 403 | 30/8 | +5.46 pp [2.48, 8.44] | 0.000472 | formal primary; same bounded claim for Mistral |
| MAIN-03 | Qwen, PROPER vs Dense | 366 vs 335 | 31/0 | +7.69 pp [5.21, 10.42] | 3.73e-9 | formal key secondary; PROPER outperforms frozen Dense baseline |
| MAIN-04 | Mistral, PROPER vs Dense | 180 vs 166 | 23/9 | +3.47 pp [0.74, 6.20] | 0.0201 | formal key secondary |
| MAIN-05 | Qwen, PROPER vs LLM Judge | 366 vs 326 | 45/5 | +9.93 pp [6.70, 13.40] | 1.26e-8 | formal key secondary |
| MAIN-06 | Mistral, PROPER vs LLM Judge | 180 vs 160 | 30/10 | +4.96 pp [1.99, 7.94] | 0.00444 | formal key secondary |

These rows do **not** support cross-benchmark, multi-step, causal, or universal claims; the evaluated setting is one post-failure recovery decision on one benchmark and one fixed memory bank.

## Failure-stratum evidence

Population sizes are 152 argument-omission, 146 transient-authorization, and 105 timeout members of the changed-target union. Source fields are the `stratified_primary_exploratory` rows. These rows are exploratory even though Holm-adjusted values were computed.

| ID | Model / stratum | TF-IDF → PROPER | +/− | RD, 95% CI | Interpretation |
|---|---|---:|---:|---|---|
| STR-01 | Qwen / argument omission | 136 → 146 / 152 | 10/0 | +6.58 pp [3.29, 10.53] | positive, concentrated stratum effect |
| STR-02 | Qwen / transient authorization | 117 → 122 / 146 | 5/0 | +3.42 pp [0.68, 6.85] | positive descriptive direction; exploratory Holm p=0.25 |
| STR-03 | Qwen / timeout | 98 → 98 / 105 | 0/0 | 0.00 pp [0, 0] | explicit selection-to-behavior gap |
| STR-04 | Mistral / argument omission | 95 → 114 / 152 | 25/6 | +12.50 pp [5.92, 19.74] | positive exploratory effect |
| STR-05 | Mistral / transient authorization | 0 → 0 / 146 | 0/0 | 0.00 pp [0, 0] | all memory conditions fail in this stratum |
| STR-06 | Mistral / timeout | 63 → 66 / 105 | 5/2 | +2.86 pp [−1.90, 7.62] | weak/uncertain descriptive direction |

Allowed: effects vary substantially by model and failure stratum. Not allowed: the method works uniformly across failure types.

## Ablation and mechanism evidence

Formal ablation source is the `core_ablations` family in the formal tables. Intervention-only diagnostics are descriptive and come from `outputs/paper_2026/e4_diagnostics/diagnostics.json`, SHA256 `b74f355fff9cef82c257fe7ef2d887017526e3093122dc0d2de555a5734991d4`, field `intervention_rows`.

| ID | Number | Definition / model | Status | Allowed claim |
|---|---:|---|---|---|
| ABL-01 | +9.68 pp, 42/3, Holm p=3.46e-9 | full PROPER vs no-gate, Qwen, n=403 | formal | strong evidence that the conservative gate contributes on Qwen |
| ABL-02 | +2.48 pp, 14/4, Holm p=0.0927 | full PROPER vs no-gate, Mistral, n=403 | formal | directionally consistent but multiplicity-adjusted evidence is inconclusive |
| ABL-03 | −1.24 pp, 0/5, Holm p=0.125 | full PROPER vs no-contradiction, Qwen, n=403 | formal | no independent positive evidence for contradiction checking |
| ABL-04 | +0.99 pp, 5/1, Holm p=0.219 | full PROPER vs no-contradiction, Mistral, n=403 | formal | no stable cross-model effect |
| MEC-01 | 95 interventions; +41.05 pp Qwen, +10.53 pp Mistral | gate-selected-memory identities differ; intervention subset | descriptive/post-selection | gate benefit is concentrated where it actually changes selection |
| MEC-02 | 36 interventions; −13.89 pp Qwen, +11.11 pp Mistral | contradiction-selected-memory identities differ | descriptive/post-selection | direction conflict; contradiction is a risk-control rule, not a validated standalone contribution |

## Memory versus No Memory and observable risk

Source: E4 `risk_rows`, changed-target union, all strata. These comparisons are descriptive; no additional inferential family was declared.

| ID | Model / method | No Memory → method | +/− | RD | Other observed regressions | Interpretation |
|---|---|---:|---:|---:|---|---|
| RISK-01 | Qwen / PROPER | 268 → 366 / 403 | 105/7 | +24.32 pp | 0 safety, 0 repeated-invalid, 0 parse regressions | memory is helpful for this model/settings, but negative transfer is not absent |
| RISK-02 | Mistral / PROPER | 195 → 180 / 403 | 34/49 | −3.72 pp | 0 safety, 53 repeated-invalid, 23 parse regressions | PROPER beats other memory selectors yet memory itself is harmful overall for Mistral |
| RISK-03 | Qwen / TF-IDF | 268 → 351 / 403 | 93/10 | +20.60 pp | 0 safety regressions | history can help substantially |
| RISK-04 | Mistral / TF-IDF | 195 → 158 / 403 | 24/61 | −9.18 pp | 58 repeated-invalid, 11 parse regressions | the same memory-use pattern can hurt another model |

No condition recorded a safety violation in this benchmark. This is an absence-of-observed-events statement, not evidence of safety in deployment.

## Concentration and robustness evidence

Source: `outputs/paper_2026/e5_concentration/concentration.json`, SHA256 `782b7d8f257d01efa93d5b70e59b3d87f662b474e227649c8409c31db964b5a2`, fields `concentration_summaries`, `group_rows`, and `leave_one_group_out_rows`. All are descriptive exclusion sensitivities; no retraining or reselection occurs.

| ID | Number | Model / grouping | Allowed interpretation |
|---|---:|---|---|
| CONC-01 | 66.7% of positive transfers; leave-out RD +1.43 pp | Qwen / failed tool `get_doc` | Qwen gains are concentrated, but remain positive after removing `get_doc` |
| CONC-02 | 66.7%; leave-out RD +1.32 pp | Qwen / selected memory M058 | same bounded concentration claim |
| CONC-03 | 36.7%; leave-out RD +3.14 pp | Mistral / failed tool `validate_cron` | less tool-concentrated than Qwen |
| CONC-04 | 26.7%; leave-out RD +3.59 pp | Mistral / selected memory M089 | no single selected memory explains the full effect |
| CONC-05 | zero sign reversals | every single tool, task-domain, or selected-memory exclusion, both models | primary paired effect remains positive under each one-group exclusion; this is not out-of-distribution robustness |

## Evaluation reliability and V1

Source: `outputs/paper_2026/evaluator_blind_audit/manifest.json`, SHA256 `8bbea707aa71a9f897ef7ee0fef1251e0c6f65344d253d89c0e21c3b2c38c3d9`; preparation lock `configs/paper_2026/evaluator_blind_audit_v1_0.preparation.lock.json`.

- 4,306 unique formal pairs; all 280 discordant pairs plus 819 stratified non-discordant pairs were selected, for 1,099 blinded review pairs and 1,743 unique logical decisions.
- Reviewer A and B templates each contain 1,099 rows and currently contain zero labels.
- **TODO-V1:** no human accuracy, agreement rate, Cohen's kappa, disagreement adjudication, or evaluator-validity conclusion exists yet.
- Until V1 is complete, automated Recovery Validity is the frozen endpoint but its human reliability is an explicit submission limitation.

