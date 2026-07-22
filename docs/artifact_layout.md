# Artifact and runtime layout

This repository separates immutable experiment-time identity records from the
post-result runnable tree. This prevents cleanup refactors from being presented as
if they had existed before model outputs were generated.

## Formal identity records

These files retain their exact experiment-time bytes:

- `configs/applicability_intervention_gate.yaml`
  - SHA-256: `58e81038ae445c4c99ee822d5e6ca9dbd226e9df0ccef98df34fc2cd279ee25e`
- `configs/applicability_intervention_gate.lock.json`
  - SHA-256: `1a6d8d0cb669f864632c42ee2c4776e9acb732ac09289959d01ba6ef2acd1a32`
- `configs/confirmatory_gate_v1.yaml`
  - SHA-256: `781f8305162840e6ce6e3ca43890255ace0bda4e3108997e2b62d92a085423f1`
- `configs/confirmatory_gate_v1.lock.json`
  - SHA-256: `07d9d603414a2618f9a9ec21ab5eb9ca49b59548a9908ce579ce90a8fed5ccff`
- `configs/toolmisusebench_source.sha256`
  - SHA-256: `acb27f19331bf716d39a5ceee3556107da9c5d14d8d8e235ab4b5d30ace7b39b`

The slim tree intentionally removed several files named by these historical
records. They are identity evidence, not current execution entry points. The
complete pre-cleanup workspace is retained separately by the project owner.

## Runnable post-result tree

Current scripts use:

- `configs/applicability_intervention_gate.runtime.yaml`
- `configs/applicability_intervention_gate.runtime.lock.json`
- `configs/confirmatory_gate_v1.runtime.yaml`
- `configs/confirmatory_gate_v1.runtime.lock.json`
- `configs/toolmisusebench_source.runtime.sha256`
- `configs/memory_bank.yaml`
- `configs/candidate_development.yaml`

Runtime files preserve the method behavior while using generic module and artifact
names. Their status fields explicitly state that they were refactored after the
completed results. They must not be cited as preregistered experiment-time files.

## Immutable results

`configs/confirmatory_gate_v1.result.lock.json` verifies the raw model results,
prepared cohort, screening output, lab log, independent analysis, and tool table.
The cleanup does not modify any of those locked artifacts.

Future broad-applicability experiments must create a new protocol, configuration,
lock, output directory, and exclusion manifest. They must not overwrite or retune
the v1 formal or runtime artifacts.
