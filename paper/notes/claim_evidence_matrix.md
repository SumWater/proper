# Claim--evidence matrix

| Claim candidate | Evidence | Level | Allowed wording | Prohibited wording |
|---|---|---|---|---|
| PROPER improves over TF-IDF on the changed-target union for both evaluated models. | MAIN-01, MAIN-02 | formal primary | “improved paired Recovery Validity by 3.72 and 5.46 percentage points” | “universally improves agents” |
| PROPER outperforms the frozen Dense and LLM-Judge baselines. | MAIN-03--MAIN-06 | formal key secondary | bounded to models, benchmark, memory bank, and one-step horizon | “better than neural retrieval/LLM judges in general” |
| Effects are heterogeneous across failure strata. | STR-01--STR-06 | exploratory/descriptive | explicitly report both zeros and weak cells | “works across all failure types” |
| Conservative gating is the clearest validated component. | ABL-01, ABL-02, MEC-01, SEL-05 | mixed formal + descriptive | strong Qwen evidence, directionally consistent but inconclusive Mistral evidence | “the gate is always necessary” |
| Contradiction checking is not independently validated by the behavioral ablation. | ABL-03, ABL-04, MEC-02 | formal null/inconsistent + descriptive | present as conservative design/risk control with inconclusive incremental benefit | list contradiction as a separately proven contribution |
| Historical memories can help or hurt depending on the model and condition. | RISK-01--RISK-04, STR-03, STR-05 | descriptive | Qwen benefits; Mistral memory methods do not beat No Memory overall | causal claims about why every model changes behavior |
| PROPER reduces selector-label errors relative to TF-IDF without introducing new labeled errors. | SEL-02, SEL-03 | descriptive, V1-sensitive | “under the frozen automated applicability labels” | “perfect selection precision” |
| No safety violations were observed. | formal descriptive rows, E4 risk rows | descriptive absence of events | “zero observed safety violations in these 8,656 logical rows” | “PROPER is safe” |
| Qwen gains are concentrated but not wholly explained by one tool or memory. | CONC-01, CONC-02, CONC-05 | descriptive sensitivity | state exact leave-one-out residual RD | general robustness or causal invariance |
| Mistral gains over TF-IDF are more distributed by tool/memory, but memory remains worse than No Memory overall. | CONC-03, CONC-04, RISK-02 | descriptive | preserve both facts together | suppress the No-Memory result |
| Automated evaluator decisions are reliable. | V1 packet only; no labels | unsupported until V1 | `TODO-V1: blinded evaluator audit and inter-annotator agreement` | any accuracy, agreement, or kappa number |
| PROPER generalizes beyond the frozen benchmark or to multi-step agents. | none in P0--E5 | unsupported | list as future work/limitation | any Tau3/E6-derived or external-generalization claim |

## Frozen contribution ceiling

The paper may claim at most three contributions:

1. An observable-evidence, conservative selector that separates applicability support, preconditions/tool compatibility, contradiction signals, and an explicit replacement gate under a fail-closed interface.
2. A controlled two-model, three-stratum comparison against No Memory, TF-IDF, Dense, a fixed LLM Judge, Oracle, and two component ablations, with paired inference on a pre-frozen changed-target population.
3. An evidence-bounded diagnosis showing model/failure heterogeneity, negative transfer, selection-to-behavior gaps, and concentration/leave-one-group-out sensitivities.

The contradiction component must not be advertised as independently validated; its incremental behavioral evidence is inconsistent.

