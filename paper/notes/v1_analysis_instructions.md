# V1 analysis procedure

Run the following only after both human reviewers have independently completed their respective CSV files and the two completed files have been finalized:

```bash
python paper/scripts/analyze_v1_blind_audit.py \
  --reviewer-a outputs/paper_2026/evaluator_blind_audit/reviewer_packet/reviewer_a.csv \
  --reviewer-b outputs/paper_2026/evaluator_blind_audit/reviewer_packet/reviewer_b.csv
```

Outputs are `paper/generated/v1_blind_audit_report.json` and `paper/generated/v1_blind_audit_disagreements.csv`.

The script verifies pair-ID alignment, reports label coverage, calculates exact agreement and unweighted Cohen's kappa for every jointly completed label field, and compares endpoint labels with the frozen automatic endpoint encoded in the anonymous packet. It never reads the sealed key and never accepts a Qwen preview as an input.

If either reviewer is incomplete, the report status is `incomplete_human_labels_no_formal_v1_conclusion`; do not quote reliability statistics as final evidence in that state.
