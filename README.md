# PROPER Gate

PROPER Gate is a conservative applicability gate for selecting recovery memories
for tool-using agents. TF-IDF first retrieves candidate experiences; the frozen
gate replaces Rank-1 only when observable failure and candidate features indicate
that a compatible alternative is available. Otherwise it preserves Rank-1.

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

## Active direction

The next stage investigates whether the same applicability-gating idea extends
across tools, memories, and observable failure families. New development and
confirmation data must remain separated from the frozen public-test result.
The CPU-only capacity audit found that authorization has the strongest new
candidate capacity but requires a repeated-denial observation; see
`docs/extension_capacity_audit_result.md`.
Because probing a persistent denial would violate the safety contract, the
next frozen CPU audit is restricted to the released transient-authorization
stratum; see `docs/transient_authz_capacity_v1_protocol.md`.

## Repository map

- `src/failure_memory/intervention_gate.py`: observable gate features
- `src/failure_memory/frozen_gate.py`: frozen dependency-free inference
- `experiments/applicability_intervention_gate.py`: development cross-validation
- `experiments/confirmatory_gate_v1.py`: frozen model experiment
- `experiments/extension_capacity_audit.py`: CPU-only cross-failure capacity audit
- `experiments/transient_authz_capacity_v1.py`: native transient-authz capacity preparation
- `outputs/proper_gate/`: frozen gate-development artifact
- `outputs/candidate_selection/`: frozen candidate-ranking artifact
- `outputs/confirmatory_gate_v1/`: immutable formal results and analysis
- `docs/preregistration_confirmatory_gate_v1.md`: frozen protocol
- `docs/confirmatory_gate_v1_result.md`: formal result and limitations

Formal experiment identities and post-result runnable configurations are kept
separate. Files without `.runtime` retain the exact experiment-time bytes;
`.runtime` files drive the slim-tree code after cleanup. See
`docs/artifact_layout.md` before running or extending an experiment.

Reusable experiment support is organized as agent runtime, benchmark-instance,
memory-bank, candidate-selection, and paired-evaluation modules. Historical pilot
entry points and stopped reranker branches are intentionally excluded.

## Local checks

```bash
python -m unittest discover -s tests -v
python -m compileall -q src experiments tests
```

The exact benchmark, environment, model, source, and result identities are stored
under `configs/`. Temporary datasets and lab logs remain under `work/`.
