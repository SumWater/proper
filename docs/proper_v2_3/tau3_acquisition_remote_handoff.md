# Remote one-shot tau3 acquisition handoff

## Synchronize once

Synchronize these folder-level units to the existing remote project checkout,
then create one remote commit containing the synchronized changes:

- `configs/proper_v2_3/`
- `docs/proper_v2_3/`
- `experiments/proper_v2_3/`
- `schemas/proper_v2_3/`
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
