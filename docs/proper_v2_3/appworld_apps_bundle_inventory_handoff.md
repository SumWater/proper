# AppWorld apps-bundle inventory handoff

Synchronize the next single v2.3 handoff archive into the existing remote
project and commit it. The already verified wheel must remain at:

`/home/amax/proper-inputs/appworld/appworld-0.1.3.post1-py3-none-any.whl`

From the clean remote project root, run exactly once:

```bash
work/proper_v2_3_tau3_replay_smoke_venv/bin/python experiments/proper_v2_3/run_appworld_apps_bundle_inventory_remote_v2_3.py --expected-project-revision "$(git rev-parse HEAD)" --wheel /home/amax/proper-inputs/appworld/appworld-0.1.3.post1-py3-none-any.whl
```

This decrypts only `apps.bundle` in memory and outputs aggregate/hash evidence.
It performs no extraction, installation, tests-bundle read, data download,
task/API read, model load, or GPU operation. Do not rerun after either success
or failure. Return the one new directory under
`outputs/proper_v2_3/appworld_apps_bundle_inventory_remote/`.
