# Storyline and contribution candidates

## One-sentence research question

When a tool-using LLM agent fails, can a selector grounded only in observable failure evidence decide when to replace similarity-ranked historical memory so that one-step recovery improves without hiding negative transfer or unsupported applicability assumptions?

## Storyline

1. Similar historical failures are not automatically useful: memory changes the agent prompt and may either repair the failure or induce a mismatched/repeated action.
2. PROPER treats retrieval as a proposal, not an instruction. It evaluates candidate applicability using observable triggers, preconditions, repair-target/tool compatibility, and contradiction evidence, then changes Rank-1 only under a conservative replacement gate.
3. The primary evidence is relative rather than universal: PROPER beats TF-IDF, Dense, and a fixed LLM Judge on the frozen changed-target union for both models.
4. Absolute memory utility is model-dependent. Qwen benefits strongly from memory, whereas every tested memory method remains below No Memory overall for Mistral; some strata have exact zero effects.
5. The gate is the clearest supported mechanism. Contradiction checking changes risky selections but lacks stable independent behavioral benefit.
6. Gains are heterogeneous and, for Qwen, concentrated, yet the primary direction survives every single tool/domain/memory exclusion. The claim therefore remains benchmark- and setting-bounded.

## Core contributions (maximum three)

1. **Method:** a fail-closed, observable-only failure-memory selector with explicit evidence support, compatibility/precondition checks, contradiction auditing, and conservative Rank-1 replacement.
2. **Evaluation:** a frozen two-model, three-failure-stratum paired evaluation against retrieval, LLM-reranking, no-memory, oracle, and component-ablation controls.
3. **Diagnosis:** a risk-centered analysis of negative transfer, gate interventions, model/failure heterogeneity, selection-to-behavior gaps, and effect concentration.

## Title candidates

1. **When Failure Memories Help or Hurt: Conservative Selection for Tool-Using LLM Agents**
2. **PROPER: Observable-Evidence Selection of Failure Memories for Tool-Using Agents**
3. **Retrieval Is Not Applicability: Conservative Failure-Memory Selection for LLM Agents**
4. **Conservative Failure-Memory Selection under Observable Tool-Execution Evidence**

Recommended working title: candidate 1. It matches the strongest evidence while foregrounding the important Mistral/No-Memory limitation.

## Table and figure roles

- Main result table: answer whether PROPER improves Recovery Validity and how absolute performance compares with No Memory and Oracle.
- Paired-effect table: answer the primary and strong-baseline RQs with discordant counts, CIs, and corrected p-values.
- Cross-stratum table/figure: expose argument-omission gains, timeout gaps, and Mistral authorization failure rather than average them away.
- Ablation table: isolate gate and contradiction components; make the contradiction null/inconsistency visible.
- Risk table: show positive and negative transfer, repeated-invalid and parse regressions relative to No Memory.
- Concentration table/figure: identify dominant tools/memories and report leave-one-group-out residual effects.
- Method figure (future F1 asset): observable state + TF-IDF Top-10 → candidate checks → conservative gate → keep/select/abstain; no hidden labels or benchmark names.

