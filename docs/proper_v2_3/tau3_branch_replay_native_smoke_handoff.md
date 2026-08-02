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

Run from the remote project root in its Python 3.12 tau3 environment:

```bash
python experiments/proper_v2_3/run_tau3_branch_replay_native_smoke_remote_v2_3.py --expected-project-revision "$(git rev-parse HEAD)"
```

Stop if the command fails. A passing result authorizes design of the public
branch capture protocol only; it does not authorize a model runner or GPU run.
