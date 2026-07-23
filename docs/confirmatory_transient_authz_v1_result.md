# Confirmatory Transient Authorization v1 Result

## Formal result

The frozen Qwen3-8B run completed on 175 released transient-authorization
targets without parse failures. The preregistered primary population contained
the 53 targets where PROPER changed TF-IDF Rank-1 before model execution.

In the primary population, TF-IDF Rank-1 achieved Recovery Validity on 34/53
targets (64.15%), while PROPER achieved 49/53 (92.45%). There were 15 paired
improvements and no paired deterioration, for a paired risk difference of
+28.30 percentage points (95% paired Wald CI: +16.06 to +40.55). The exact
two-sided McNemar p-value was 0.000061. The frozen directional hypothesis was
therefore supported.

Across all 175 valid targets, including 122 unchanged-memory pairs, Recovery
Validity increased from 144/175 (82.29%) to 159/175 (90.86%), a descriptive
+8.57 percentage-point difference. Neither condition produced a Safety
Violation or repeated invalid call.

## Effect distribution

The 15 improvements span five target tools: `get_doc` (5), `read_file` (4),
`write_file` (3), `search_docs` (2), and `validate_cron` (1). They use seven
different selected memories; the largest single memory contributes 5/15
improvements. Thus this result is not the single-tool, single-memory
concentration observed in the earlier argument-omission experiment.

All beneficial selections exposed a memory whose observable text encoded a
retry policy. Nine selected memories were originally TF-IDF Rank 2, five were
Rank 3, and one was Rank 5.

## Supported claim and limitations

The result supports the claim that a frozen, observable-feature memory selector
can improve recovery-memory choice across multiple tools and memories within
ToolMisuseBench's released transient-authorization condition. Together with the
earlier argument-omission result, it provides evidence across two observable
failure settings.

It does not establish universal Agent-memory applicability. The experiment uses
one model, one benchmark, one-step recovery, and a released transient condition.
Persistent authorization is excluded for safety. Public-test inputs were used
for CPU-only capacity screening, so this is a model-output holdout rather than
an unseen-input holdout. These boundaries must remain explicit in the paper.
