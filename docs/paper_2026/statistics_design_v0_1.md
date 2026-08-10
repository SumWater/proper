# Paper statistics design v0.1

- Status: development candidate before protocol freeze
- Opened: 2026-08-09
- Configuration: `configs/paper_2026/statistics_v0_1.yaml`
- Implementation: `src/failure_memory/paper_2026/statistics.py`

## Endpoint and effect

The primary endpoint is paired binary Recovery Validity. For every treatment--baseline comparison,
the analysis reports the treatment-minus-baseline paired risk difference, positive discordant count
(`baseline=0, treatment=1`), negative discordant count (`baseline=1, treatment=0`), and the exact
two-sided McNemar binomial p-value. A zero-discordance comparison has p-value 1.

The 95% confidence interval is a paired-instance percentile bootstrap with 10,000 replicates. Each
analysis cell receives a deterministic seed derived from SHA-256 of
`20260809:<analysis_id>`, so reruns are reproducible without reusing one random stream across cells.

## Multiplicity families

Holm correction is applied separately to three families fixed before new formal outputs:

1. Primary: PROPER versus TF-IDF in all six model-by-failure-stratum cells.
2. Key secondary: PROPER versus Dense and PROPER versus LLM Judge in the same six cells (12 tests).
3. Ablation: PROPER versus PROPER-no-gate and PROPER versus PROPER-no-contradiction in the same six
   cells (12 tests).

Oracle is descriptive and is not hypothesis-tested. Tool, memory, leave-one-out, and other subgroup
analyses remain descriptive unless a later protocol version declares a separate family before formal
outputs are inspected.

## Verification

Six statistics tests pass under local Python 3.12.7. They reconstruct the frozen historical tables:

- argument omission: TF-IDF 99/115, PROPER 109/115, discordance 10/0;
- transient authorization: TF-IDF 34/53, PROPER 49/53, discordance 15/0.

The tests also cover zero discordance, deterministic bootstrap output, order-independent Holm
adjustment, and rejection of non-binary outcomes. These tests verify arithmetic and invariants; they
do not authorize new model inference or convert historical results into prospective evidence.
