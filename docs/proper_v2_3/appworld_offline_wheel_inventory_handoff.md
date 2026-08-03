# AppWorld wheel-inventory handoff

## Inputs

Synchronize the current tracked v2.3 stage at one folder-level boundary. Keep
the official wheel outside the PROPER project, for example:

`/home/amax/proper-inputs/appworld/appworld-0.1.3.post1-py3-none-any.whl`

The wheel must be the official 625,317-byte PyPI artifact with SHA-256
`db77f8003982502383a50fa2974983894bd1c54f64e2fd3f7e1540d5edd037eb`.
Do not unpack, rename, install, or place it inside the project checkout.

## One command

After committing the synchronized v2.3 files and confirming a clean tracked
worktree, run from the remote project root:

```bash
work/proper_v2_3_tau3_replay_smoke_venv/bin/python experiments/proper_v2_3/run_appworld_offline_wheel_inventory_remote_v2_3.py --expected-project-revision "$(git rev-parse HEAD)" --wheel /home/amax/proper-inputs/appworld/appworld-0.1.3.post1-py3-none-any.whl
```

This command performs no download, installation, extraction, decryption, task
read, model load, or GPU operation. Return the one newly created directory
under `outputs/proper_v2_3/appworld_wheel_inventory_remote/` for local freeze.

If preflight or inventory fails, preserve and return that result. Do not replace
the wheel, change the expected identity, or rerun without first freezing the
failure.
