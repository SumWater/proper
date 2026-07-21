# ToolMisuseBench compatibility audit

Status: **passed with mandatory adapter and deterministic prefix replay for the bounded pilot**. See `compatibility_decision.md`. This does not approve formal/large-scale experiments; those still require an exact Python 3.11+ environment lock.

Incremental evidence and decisions are recorded in `audit_findings.md`.

## Current first-party observations (2026-07-21)

- arXiv v1 (submitted 2026-04-02) describes 6,800 tasks and replayable fault injection.
- The GitHub default branch is `master`; its visible README quickstart still generates/evaluates `v0.1` and describes 5,000/800/1,000 splits.
- The Hugging Face repository `main` currently contains a newer `data/` and `artifacts/` addition described as v0.2, while root-level `manifest.json` and `v0_1_freeze.json` remain v0.1 artifacts. Therefore repository `main` is not itself a sufficient release identifier.
- The Hugging Face viewer has reported schema-casting problems; viewer output must not substitute for raw-file validation.

These are audit inputs, not frozen facts. Metadata sources:

- https://arxiv.org/abs/2604.01508
- https://github.com/akgitrepos/toolmisusebench
- https://huggingface.co/datasets/sigdelakshey/ToolMisuseBench

## Evidence checklist

| Area | Test/evidence required | Pass criterion | Critical |
|---|---|---|---|
| Code identity | Record remote HEAD, chosen commit, branch/tag, clean tree | Full 40-char commit is frozen | yes |
| Data identity | Record HF commit SHA, release directory, export manifest hash | Immutable revision and unambiguous release are frozen | yes |
| Code/data compatibility | Inspect loaders/schemas; run a tiny representative sample | Chosen code parses and evaluates chosen data with no coercion or silent defaults | yes |
| Manifest integrity | Verify manifest schema, sizes, and SHA-256 for every selected file | Every selected artifact matches its manifest | yes |
| Dependencies | Freeze Python, OS, package lock, and native tool versions | Clean reinstall passes tests | yes |
| Deterministic replay | Repeat fixed task/seed/fault plan >=3 times; canonicalize traces | State transitions, injected fault, actions, scores, and trace hash match | yes |
| Snapshot/fork | Locate serialization/clone API and test branch independence | Same failure state can fork without cross-branch mutation | no |
| Prefix fallback | Recreate failure state from initial state and fixed action prefix | Canonical pre-failure state/observation hashes match | yes if snapshot fails |
| Observation boundary | Trace the object passed to `Agent.act` and prompt/adapter serialization | Only declared public observation fields reach agent | yes |
| Hidden-field leakage | Search data plumbing and instrument runtime for forbidden keys/values | `fault_plan`, `fault_type`, `gold_summary`, `success_criteria`, seeds/oracles are absent | yes |
| Fault semantics | Inspect timeout, schema/argument, authz injectors | Transient vs persistent behavior is explicit and reproducible | yes |
| Recovery contract | Add external evaluator over immutable traces | `G`, `I`, and `B` can be checked deterministically | yes |
| Correct stop | Evaluate structured stop/reason and forbidden later actions | Independent deterministic result, no official scorer changes | yes |
| Official task success | Capture baseline scorer and compare after metric-layer attachment | Official output remains unchanged | yes |

## Minimal audit sample

Select at least two tasks per initial failure class and include easy/hard cases where available. Selection must be by frozen task IDs before viewing outcome differences. Do not download a full release until metadata identifies the intended release and code compatibility has been inspected.

For each task, retain canonical JSON hashes for: source row, agent-visible observation, action sequence, injected failures, state before failure, terminal state, official score, and recovery metrics. Canonicalization must sort object keys and exclude only a predeclared list of nondeterministic presentation fields.

## Leakage audit method

1. Static: follow dataset row -> loader -> environment -> observation -> agent adapter/prompt.
2. Runtime: wrap `Agent.act`, serialize the exact received value, and scan both keys and distinctive hidden-field values.
3. Negative controls: plant harmless sentinel values in evaluator-only fields in a local tiny fixture; assert none reach the agent-visible object.
4. Record intentional disclosures separately; provenance annotations are never implicitly public.

## Decision record

The audit report must conclude `PASS`, `PASS_WITH_PREFIX_REPLAY`, or `STOP`, with evidence paths for every critical row. Missing evidence is `UNVERIFIED`, never an assumed pass.
