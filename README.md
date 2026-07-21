# Failure Memory

**Working title:** *When Similar Failures Need Different Fixes: Evaluating Provenance-Conditioned Experience Transfer in Tool-Using Agents*

This repository is an independent, reproducible workspace for a two-week stop-loss pilot. Its first gate is a compatibility audit of ToolMisuseBench; it is not yet a full paper system.

## Research question

The pilot asks whether natural-language experience retrieval selects recovery advice that is inapplicable to the current failure, whether following that advice causes measurable negative transfer, and whether failure provenance provides useful evidence for applicability. The causal/measurement chain is kept explicit:

`Failure provenance -> recovery-policy applicability -> agent behavior -> memory utility`

Provenance is evidence about applicability, not applicability itself. Final task success is also not recovery applicability.

## Two-week stop-loss gates

1. **Compatibility (days 1-2):** freeze a mutually compatible code commit and dataset revision; test deterministic replay, snapshot/failure-prefix replay, field isolation, recovery-contract evaluation, and correct-stop evaluation.
2. **Feasibility:** test whether a natural memory pool yields enough selected/exposed inapplicable experiences and whether agents follow them.
3. **Signal:** compare paired outcomes against No Memory and estimate the Oracle Provenance/Applicability headroom.

Stop if replay is unstable, hidden fields leak, correct stop cannot be evaluated reliably, inapplicable retrieval is too rare, or harmful utilization has no measurable paired signal. Do not build a Predicted Provenance Gate unless an oracle gate shows useful headroom.

## Scope

The first round covers transient timeout, recoverable schema/argument failure, and persistent authorization denial. It defines three structured recovery policies: `retry(max_attempts)`, `revise_arguments(operation, fields, bindings)`, and `stop_and_report(reason_code)`.

Out of scope now: fine-tuning, LoRA, reinforcement learning, active-diagnosis agents, complex Failure Cards, large-scale/GPU runs, a second model, and Predicted Provenance Gate.

## Workflow

- **Windows/Codex:** edit repository files, run static checks and unit tests.
- **WSL/Ubuntu:** run Linux-only development and small CPU experiments using relative paths. Write temporary output under `work/`.
- **Lab Linux:** only after the audit passes, run formal experiments; do not commit environments, full datasets, models, secrets, or large rollouts.

Project code must not assume a Windows path or call `wsl.exe`.

## Local checks

```bash
python -m unittest discover -s tests -v
python -m compileall -q src tests
```

See `docs/research_protocol.md` for definitions and stop rules, `docs/compatibility_audit.md` for the evidence checklist, and `docs/compatibility_decision.md` for the completed first-stage decision.

## Current compatibility decision

The initial audit concluded **PASS WITH ADAPTER AND DETERMINISTIC PREFIX REPLAY**. The frozen v0.2 code/data identities and mandatory conditions are recorded in `configs/toolmisusebench.lock.json`; the evidence-backed decision is in `docs/compatibility_decision.md`. This permits only the bounded memory-feasibility pilot. Formal experiments still require a fresh exact dependency lock under Python 3.11+.

## Current phase

The deterministic CPU retrieval-feasibility preflight passed its frozen gate: 20 of 120 queries selected and exposed an inapplicable rank-1 experience. The active gate is now paired agent utilization on those 20 instances, comparing No Memory with Source-Blind rank-1 Memory from the same deterministic failure prefix. The research agent is fixed to a locally downloaded Qwen3-8B with thinking disabled and deterministic decoding. Followed Inapplicability and Harmful Utilization thresholds are frozen in `configs/agent_utilization.json`. The model-backed integration smoke test passed; the exact Python 3.11 lab environment and model artifacts are frozen in `configs/lab_environment.lock.json` and `configs/qwen3_8b_model.sha256` before the research-gate run.
