# PROPER v2.3 tau3 remote CPU execution handoff

## Authority boundary

This workstation is code-authoring only. The artifacts committed in `42de557`
under `outputs/proper_v2_3/tau3_branch_screen/` are implementation self-tests,
not formal remote evidence. They remain preserved and are never overwritten.

The only formal result for this gate must be produced on the execution computer
under a unique directory in
`outputs/proper_v2_3/tau3_branch_screen_remote/`.

This is still a development scripted branch screen. A passing remote result is
not selector evidence, model completion evidence, held-out evidence, or a
confirmatory result. New held-out capacity remains zero.

## Folder-level synchronization list

Synchronize these folders together from one exact Git commit:

- `configs/proper_v2_3/`
- `docs/proper_v2_3/`
- `experiments/proper_v2_3/`
- `schemas/proper_v2_3/`
- `src/failure_memory/proper_v2/`
- `tests/`

Do not synchronize the local `outputs/proper_v2_3/tau3_branch_screen/` files as
remote evidence. The execution entry point acquires `external/tau2-bench` only
when it is missing and rejects any checkout other than the pinned revision.

## Single remote command

Run exactly one command from the repository root after replacing the placeholder
with the full handoff commit SHA:

```text
python experiments/proper_v2_3/run_tau3_remote_v2_3.py --expected-project-revision <HANDOFF_COMMIT_SHA>
```

The command creates a fresh uniquely named isolated environment under `work/`,
installs the exact top-level CPU dependencies, applies the no-CUDA guard, verifies both Git
revisions, runs the native branch screen, validates its schema, and runs the
complete repository test suite.

## Returned artifacts

Return the entire newly created run folder containing:

- `branch_screen.json`: the raw 12-pair result and complete ledgers;
- `remote_validation.json`: host, Python, resolved packages, input manifest,
  project/tau revisions, test result, boundary flags, raw-result hash, and the
  next gate.

Do not rerun into the same directory and do not edit a failed result. Each run
gets a UTC/host/revision-qualified directory; a failed run is preserved as
negative development evidence.

## Acceptance gate

Remote acceptance requires all of the following:

- exact handoff project revision and clean tracked worktree;
- tau revision `fc0055dc4e0a316c3f83133267fbd6faaa770992`;
- Python 3.11 or 3.12 and `CUDA_VISIBLE_DEVICES=-1`;
- branch screen 12/12, including four pairs per effect class;
- all repository tests and Draft 2020-12 schema validation passing;
- every exact successful-action repeat blocked;
- every non-idempotent guarded action executed exactly once and verified;
- lifecycle consumed and ordinary-planning continuation established;
- held-out capacity zero and no model/confirmatory authorization.

Only after the returned envelope passes this gate may the five-condition model
development protocol be frozen. No model runner is part of this handoff.
