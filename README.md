# PROPER Gate

PROPER Gate is a conservative applicability gate for selecting recovery memories
for tool-using agents. TF-IDF first retrieves candidate experiences; the frozen
gate replaces Rank-1 only when observable failure and candidate features indicate
that a compatible alternative is available. Otherwise it preserves Rank-1.

## Versioned layout

Completed PROPER v1 artifacts are preserved under `proper_v1` namespaces in
`configs/`, `docs/`, `experiments/`, `outputs/`, and `schemas/`. New unified
PROPER v2 work belongs under the corresponding `proper_v2` namespaces. See
`docs/proper_v2/artifact_migration.md` for the migration and immutability rules.

## Current evidence

The frozen Qwen3-8B public-test experiment contains 115 gate-changed paired
instances in the deterministic argument-omission setting:

- TF-IDF Rank-1 recovery validity: 99/115 (86.09%)
- PROPER Gate recovery validity: 109/115 (94.78%)
- paired improvement: 10; paired deterioration: 0
- paired risk difference: +8.70 percentage points
- exact two-sided McNemar p = 0.001953125

The supported claim is deliberately narrow. All observed improvements occurred
for `get_doc` and used one selected memory. The repository must not use these
public-test outcomes to retune the frozen gate.

The independently recomputed transient-authorization extension contains 53
selector-changed pairs: TF-IDF Rank-1 Recovery Validity was 34/53 and PROPER was
49/53, with 15 improvements, no deterioration, a +28.30 percentage-point paired
difference, and exact two-sided McNemar p = 0.000061. Improvements span five
target tools and seven selected memories. This supports a cross-tool,
cross-memory effect within the released transient-authorization condition, not
a universal Agent-memory claim.

## Active direction

The next stage tests memory selection on the released native transient-
authorization stratum without probing persistent denials. The frozen CPU-only
capacity audit contains 175 valid targets and a 53-pair primary population
where the conservative selector changes TF-IDF Rank-1. These changed pairs span
seven target tools and twelve selected memories. Persistent authorization is
excluded because retrying a persistent denial violates the safety contract.
The model-output protocol is frozen in
`docs/proper_v1/preregistration_confirmatory_transient_authz_v1.md`. The deterministic
Linux preparation reconstructed exactly without model output, so the single
frozen GPU run is now authorized; see
`docs/proper_v1/confirmatory_transient_authz_v1_preparation.md`.

## Repository map

- `src/failure_memory/intervention_gate.py`: observable gate features
- `src/failure_memory/frozen_gate.py`: frozen dependency-free inference
- `experiments/proper_v1/applicability_intervention_gate.py`: development cross-validation
- `experiments/proper_v1/confirmatory_gate_v1.py`: frozen model experiment
- `experiments/proper_v1/extension_capacity_audit.py`: CPU-only cross-failure capacity audit
- `experiments/proper_v1/transient_authz_capacity_v1.py`: native transient-authz capacity preparation
- `experiments/proper_v1/confirmatory_transient_authz_v1.py`: frozen paired transient-authz experiment
- `outputs/proper_v1/proper_gate/`: frozen gate-development artifact
- `outputs/proper_v1/candidate_selection/`: frozen candidate-ranking artifact
- `outputs/proper_v1/confirmatory_gate_v1/`: immutable formal results and analysis
- `docs/proper_v1/preregistration_confirmatory_gate_v1.md`: frozen protocol
- `docs/proper_v1/confirmatory_gate_v1_result.md`: formal result and limitations
- `docs/proper_v1/preregistration_confirmatory_transient_authz_v1.md`: frozen extension protocol

Formal experiment identities and post-result runnable configurations are kept
separate. Files without `.runtime` retain the exact experiment-time bytes;
`.runtime` files drive the slim-tree code after cleanup. See
`docs/proper_v1/artifact_layout.md` before running or extending an experiment.

Reusable experiment support is organized as agent runtime, benchmark-instance,
memory-bank, candidate-selection, and paired-evaluation modules. Historical pilot
entry points and stopped reranker branches are intentionally excluded.

## Local checks

```bash
python -m unittest discover -s tests -v
python -m compileall -q src experiments tests
```

The exact benchmark, environment, model, source, and result identities are stored
under `configs/proper_v1/`. Temporary datasets and lab logs remain under `work/`.
