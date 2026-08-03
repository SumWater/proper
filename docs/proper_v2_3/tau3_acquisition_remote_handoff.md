# Remote one-shot tau3 acquisition handoff

## Synchronize once

Synchronize these folder-level units to the existing remote project checkout,
then create one remote commit containing the synchronized changes:

- `configs/proper_v2_3/`
- `docs/proper_v2_3/`
- `experiments/proper_v2_3/`
- `schemas/proper_v2_3/`
- `src/failure_memory/proper_v2/v2_3/`
- `tests/`
- `outputs/proper_v2_3/acquisition_one_shot_runner_implementation/`
- `outputs/proper_v2_3/README.md`

Do not replace the whole project, do not modify `external/tau2-bench`, and do
not copy any new file into `outputs/proper_v2/`.

## One command

From the clean remote project root, after committing the synchronized files,
run exactly once:

```bash
work/proper_v2_3_tau3_replay_smoke_venv/bin/python experiments/proper_v2_3/run_tau3_acquisition_remote_v2_3.py --expected-project-revision "$(git rev-parse HEAD)"
```

The command performs its complete preflight before starting Qwen. It may take
time to hash the 16.4 GB model directory. On a passing preflight it uses CUDA
device 0 and the existing `failure-memory-pilot` Python process for Qwen3-8B.

Do not rerun the command if it exits nonzero, is interrupted, or captures fewer
than 12 branches. That is a preserved result under this one-attempt protocol,
not permission to resume. Synchronize back the single newly created directory
under `outputs/proper_v2_3/tau3_acquisition_remote/`, including
`preflight.json`, `result.json`, `worker.stderr`, and any `attempts/` files.

Do not edit the returned files. No comparison run is authorized after return;
the result must first be frozen and interpreted locally.

## Preserved import-only attempt

The first command invocation after runner implementation failed while Python
was importing `src.failure_memory.proper_v2.v2_3.acquisition_runtime`. The
folder-level sync list had omitted `src/failure_memory/proper_v2/v2_3/`, so the
remote checkout did not contain that module. The runner never reached `main`,
created no acquisition run directory, started no preflight, loaded no model,
executed no task, and used no GPU.

This is a synchronization/infrastructure failure, not an acquisition attempt
or model result. After synchronizing the omitted source folder, committing the
tracked changes, and confirming a clean worktree, one invocation of the same
command remains authorized. No method, prompt, budget, task order, model
setting, endpoint, exclusion, or scientific stop rule changed.

## Preserved dirty-worktree preflight

The next invocation reached preflight and wrote run
`20260803T064447Z-amax-8c2b38219291`. Eleven checks passed; only
`tracked_worktree_clean` failed because the four synchronized README index
files were not committed remotely. It produced zero attempts, requests,
tokens, tools, model load, task execution, or GPU use.

That result is frozen locally. After committing exactly the reported README
changes and confirming that
`git -c core.fileMode=false status --short --untracked-files=no` is empty, one
invocation of the unchanged command in this document remains authorized. Do
not invoke it if tracked status is nonempty.
