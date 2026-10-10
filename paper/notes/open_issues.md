# Open issues and triage

## Blocks the first full draft

- **Related-work evidence and bibliography:** primary-source literature still needs to be collected and checked before writing comparative novelty claims. This does not block the current evidence-led Method/Setup/Results draft, but it blocks a responsible full Introduction/Related Work.
- **Venue/template choice:** page budget and formatting target are not frozen. The current LaTeX uses a neutral `article` skeleton.
- **Method presentation audit:** the exact notation for evidence support, decisive superiority, and abstention should be checked line-by-line against `src/failure_memory/paper_2026/` before final equations are introduced. Current prose remains faithful but intentionally non-formal.

## Blocks final submission, not the initial draft

- **P0 manifest drift for one living document:** `configs/paper_2026/p0_local_sources.sha256` expects SHA256 `11810523b32619136fc3ba33f678b1ecbec3f2d759974cc82b0ca72bbcdacee4` for `docs/paper_2026/experiment_plan.md`, while baseline commit `8b844b2` and the original experiment repository contain the later status-updated file with SHA256 `ecb45833af14a0a5222b4ed0a40daa57e3f10c08f31e30210c02717d17638133`. The other 60 manifest entries pass. Do not edit the frozen manifest or revert the plan merely to silence this check; the submission reproduction package needs either the exact historical P0 document from its recorded revision or a versioned portability/audit note that separates living-plan updates from formal result identities.
- **TODO-V1 human audit:** two reviewers must independently label 1,099 pairs; templates currently contain zero labels.
- **V1 analysis implementation:** after both CSV files are frozen and hash-locked, compute per-side endpoint agreement with the sealed automated key, inter-annotator raw agreement and Cohen's kappa, confidence/unclear summaries, and an adjudication log. No such numbers exist yet.
- **Claim freeze after V1:** revise evaluator-reliability and threats-to-validity text without changing frozen model outputs or statistical numbers.
- **Citation completion and venue formatting:** required before submission.
- **Reproducibility appendix/package:** include exact commands and the paper-side provenance manifest; do not distribute sealed V1 keys prematurely.

## Can be omitted from this paper

- Any E6/Tau3 experiment, result, capacity audit, or external-generalization narrative.
- A third model, additional failure types, multi-step external benchmark, new GPU/model run, threshold sweep, or embedding sweep.
- Reinterpreting contradiction checking as a separately validated contribution.
- New hypothesis tests for E4/E5 post-hoc subgroups; current descriptive reporting is adequate.
- Claims about universal safety, causality, or out-of-distribution robustness.

## Minimal V1 operating procedure

1. Give Reviewer A only `reviewer_packet/README.md`, `review_items.jsonl`, and `reviewer_a.csv`; give Reviewer B the analogous `reviewer_b.csv`. Do not expose `sealed_key/`.
2. Each reviewer independently fills both endpoint labels (`true|false`), both visible-support labels (`supported|unsupported|unclear`), confidence (`high|medium|low`), and notes for ambiguity. Do not reorder/delete rows or edit observation/decision fields.
3. Validate allowed values and completeness, then record SHA256 for both completed CSV files before unsealing the key.
4. Compare reviewers, calculate agreement/kappa, adjudicate disagreements under a written rule, and only then compare the frozen automated endpoint with human labels.
5. Archive raw reviewer files, validation report, hashes, agreement output, and adjudication log. Replace every `TODO-V1` in the submission or retain an explicit limitation if only one reviewer completes the packet.
