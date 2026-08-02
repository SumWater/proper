# Remote native tau3 replay smoke handoff

This handoff is CPU-only. It executes one isolated native retail write against
an in-memory database and restores its checkpoint in a second environment. It
does not load a task, model, model output, or GPU.

## Folder-level synchronization

Synchronize these folders from the committed local project into the remote
project, preserving paths:

- `configs/proper_v2_3/`
- `docs/proper_v2_3/`
- `experiments/proper_v2_3/`
- `schemas/proper_v2_3/`
- `src/failure_memory/proper_v2/v2_3/`
- `tests/`
- `outputs/proper_v2_3/README.md`

Do not overwrite `external/tau2-bench`; it must remain at the pinned revision.
After synchronization, commit the tracked changes on the remote branch so the
worktree is clean.

## One complete command

Run from the remote project root in its existing Python 3.11 or 3.12 tau3
environment:

```bash
python experiments/proper_v2_3/run_tau3_branch_replay_native_smoke_remote_v2_3.py --expected-project-revision "$(git rev-parse HEAD)"
```

Stop if the command fails. A passing result authorizes design of the public
branch capture protocol only; it does not authorize a model runner or GPU run.

Protocol v1 stopped on Python 3.11.15 before importing tau3 or executing the
native action. Protocol v2 aligns this infrastructure guard with the existing
frozen tau3 remote source-checkout contract, which permits Python 3.11 and
3.12. No method, fixture action, evaluation, or scientific gate changed.

Protocol v2 then stopped before constructing the retail environment because
tau2's top-level package imports the unused batch runner, which imports
`pandas`. Protocol v3 installs a lightweight source namespace and imports only
the retail domain, data-model, and environment modules needed by this smoke.
It does not replace or modify tau2 source. No native action, task, or model ran
in the failed v2 attempt, and no scientific gate changed.
