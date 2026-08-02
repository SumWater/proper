# Remote Qwen model inventory handoff

This handoff reads and hashes the configured Qwen3-8B directory on the remote
computer. It does not import model libraries, load the model, execute a tau
task, read model output, or use a GPU.

## Folder-level synchronization

After committing this local stage, synchronize these folders into the remote
project while preserving paths:

- `configs/proper_v2_3/`
- `docs/proper_v2_3/`
- `experiments/proper_v2_3/`
- `schemas/proper_v2_3/`
- `src/failure_memory/proper_v2/v2_3/`
- `tests/`
- `outputs/proper_v2_3/README.md`

Commit the synchronized tracked changes on the remote `proper_v2_3` branch so
its tracked worktree is clean. Do not copy, move, or edit the model directory.

## One complete command

Run once from the remote project root in the existing Python 3.11 environment:

```bash
python experiments/proper_v2_3/run_qwen_model_inventory_remote_v2_3.py --expected-project-revision "$(git rev-parse HEAD)"
```

The command may take time because it reads every model byte once for SHA-256.
Do not rerun or replace a failed result. Synchronize the newly printed
`outputs/proper_v2_3/qwen_model_inventory_remote/.../inventory.json` file back
to the same local path. A passing inventory still does not authorize loading
the model, running the 12 development tasks, capturing branches, or using a
GPU; it only permits local result verification and acquisition-runtime design.
