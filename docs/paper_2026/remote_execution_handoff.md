# P0 remote experiment-machine handoff

The local workstation has no model weights. The first remote step is an environment and model inventory
only. It does not authorize model download, smoke inference, or formal agent runs.

## Synchronization scope

The recommended option is to synchronize the complete `proper` repository while excluding generated
Python caches. Do not copy model weights into the repository; Qwen remains at its existing absolute
path on the experiment machine.

For the immediate P0 inventory only, the minimum required paths are:

- `configs/paper_2026/`;
- `docs/paper_2026/`;
- `scripts/paper_2026/`;
- `configs/proper_v1/qwen3_8b_model.sha256`;
- `experiments/proper_v1/agent_runtime.py`;
- `outputs/proper_v1/confirmatory_gate_v1/results.json`;
- `outputs/proper_v1/confirmatory_transient_authz_v1/results.json`;
- `outputs/proper_v2/timeout_pair_v2/results.json`.

All of these are required by `configs/paper_2026/p0_local_sources.sha256`. Copying only the three
`paper_2026` directories will make the source check fail.

Before E1/E2 development, synchronize the full research workspace needed by the runners:

- `configs/`, `docs/`, `experiments/`, `src/`, `schemas/`, `scripts/`, and `tests/`;
- `external/toolmisusebench/`;
- frozen historical files under `outputs/proper_v1/` and `outputs/proper_v2/`;
- required prepared inputs under `work/`, especially the public-test dataset and frozen memory bank;
- root files `pyproject.toml`, `requirements.txt`, `requirements-gate.txt`, `README.md`,
  `.gitattributes`, and `.gitignore`.

Do not synchronize `__pycache__/`, `.pytest_cache/`, temporary logs, downloaded model weights, or new
remote outputs from an older run. New remote results must be written only under
`outputs/paper_2026/` and then copied back to the local workspace.

## Required repository state

Transfer or pull the repository version containing:

- `scripts/paper_2026/inventory_remote_environment.py`;
- `docs/paper_2026/protocol.md`;
- `docs/paper_2026/historical_reuse_audit.md`.

Run from the repository root. Record `git rev-parse HEAD` and `git status --short`; the inventory script
does this automatically.

Before inventory, verify the transferred P0 inputs:

```bash
sha256sum -c configs/paper_2026/p0_local_sources.sha256
```

If any entry fails or is missing, stop and resynchronize the repository. Do not regenerate a historical
result to make the check pass.

## Inventory command

Known Qwen3-8B path on the experiment machine:

```text
/home/amax/PycharmProjects/AINegoProject/src/Models/LLM/Qwen3-8B
```

Use the parent LLM directory as a scan root so the inventory can also discover a possible second agent
model. The standard Hugging Face cache is scanned automatically:

```bash
python scripts/paper_2026/inventory_remote_environment.py \
  --model-root /home/amax/PycharmProjects/AINegoProject/src/Models/LLM \
  --verify-model-dir /home/amax/PycharmProjects/AINegoProject/src/Models/LLM/Qwen3-8B \
  --model-manifest configs/proper_v1/qwen3_8b_model.sha256 \
  --output outputs/paper_2026/p0_remote_inventory.json
```

The Qwen verification reads model files to compute SHA-256 but does not load weights into CPU/GPU
memory. The expected manifest contains 15 files. `model_manifest_verification.passed` must be `true`
before historical Qwen outputs are reused.

If scanning the parent directory is not permitted or is too broad, use the exact Qwen path; this still
verifies model A but may not discover model B:

```bash
python scripts/paper_2026/inventory_remote_environment.py \
  --model-root /home/amax/PycharmProjects/AINegoProject/src/Models/LLM/Qwen3-8B \
  --verify-model-dir /home/amax/PycharmProjects/AINegoProject/src/Models/LLM/Qwen3-8B \
  --model-manifest configs/proper_v1/qwen3_8b_model.sha256 \
  --output outputs/paper_2026/p0_remote_inventory.json
```

If model locations are known, pass each root explicitly:

```bash
python scripts/paper_2026/inventory_remote_environment.py \
  --model-root /path/to/model/root \
  --model-root /another/model/root \
  --output outputs/paper_2026/p0_remote_inventory.json
```

If locations are not known, omit `--model-root`. The script checks configured Hugging Face cache
locations and the standard user cache without loading any weights:

```bash
python scripts/paper_2026/inventory_remote_environment.py \
  --output outputs/paper_2026/p0_remote_inventory.json
```

Return the following file to the local workspace:

- `outputs/paper_2026/p0_remote_inventory.json`.

Do not return model weights. Do not publish absolute machine paths in the paper; paths are used only to
prepare the execution config.

## What the inventory records

- OS, Python, Conda environment, repository commit and dirty state;
- GPU model, driver, total/free memory and CUDA visibility;
- installed Torch/Transformers/Accelerate/BitsAndBytes/SentenceTransformers versions;
- candidate local model directories and config metadata;
- chat-template availability and approximate model-directory size;
- disk availability for each scanned root.

## Selection after return

The local protocol audit will choose:

1. one non-Qwen 7B/8B-class agent model;
2. one Dense encoder;
3. one LLM Judge model or, if no separate judge is feasible, a predeclared judge policy using an
   available instruction model;
4. quantization and batch settings compatible with the GPU.

Model choice is based on availability and execution stability, never on observed PROPER results. After
these choices are written into the protocol and config lock, a small development-only smoke stage will
be prepared. Formal inference remains blocked until that stage passes.

## Second diagnostic after the first inventory

The first returned inventory found no non-Qwen agent model and incomplete package metadata. After
synchronizing the updated inventory script, run:

```bash
python scripts/paper_2026/inventory_remote_environment.py \
  --model-root /home/amax/PycharmProjects/AINegoProject/src/Models/LLM \
  --verify-model-dir /home/amax/PycharmProjects/AINegoProject/src/Models/LLM/Qwen3-8B \
  --model-manifest configs/proper_v1/qwen3_8b_model.sha256 \
  --hash-model-dir /home/amax/.cache/huggingface/hub/models--BAAI--bge-large-en-v1.5/snapshots/d4aa6901d3a41ba39fb536a557fa166f842b0e09 \
  --output outputs/paper_2026/p0_remote_inventory_v2.json
```

This diagnostic imports installed libraries, lists Conda environments, records GPU compute processes,
and hashes the selected Dense encoder. It still does not load model weights for inference or download
anything.

## Existing Conda environment probe

The second inventory confirmed that `proper-toolsandbox` lacks Torch. Before any installation, sync
`scripts/paper_2026/probe_remote_conda_envs.py` and probe likely reusable environments:

```bash
python scripts/paper_2026/probe_remote_conda_envs.py \
  --env failure-memory-pilot \
  --env AINegoProject \
  --env Nego \
  --env MMLLM-RAG \
  --env proper-toolsandbox \
  --output outputs/paper_2026/p0_conda_probe.json
```

Return `outputs/paper_2026/p0_conda_probe.json`. This command imports libraries only; it does not
install packages, mutate environments, load model weights, or run inference.

## Storage gate before model B download

The user authorized the pinned Model B download, conditional on checking remote storage first. Sync
`scripts/paper_2026/check_remote_storage.py`, then run this read-only probe from the repository root:

```bash
python scripts/paper_2026/check_remote_storage.py \
  --output outputs/paper_2026/p0_remote_storage.json
```

Return `outputs/paper_2026/p0_remote_storage.json` before running the download command. The gate checks
the exact model target, project, and Hugging Face cache filesystems and measures their current directory
sizes. It does not download weights, load a model, alter an environment, or delete any files. The
predeclared gate requires at least 25 decimal GB free and recommends at least 35 decimal GB free on the
model target filesystem.

## Environment lock capture during Model B download

This read-only capture can run while Model B downloads because it does not load a model or reserve GPU
memory. Sync `scripts/paper_2026/capture_remote_environment_lock.py`, then run:

```bash
/home/amax/miniconda3/envs/failure-memory-pilot/bin/python \
  scripts/paper_2026/capture_remote_environment_lock.py \
  --expected-prefix /home/amax/miniconda3/envs/failure-memory-pilot \
  --output outputs/paper_2026/p0_environment_lock.json
```

Return `outputs/paper_2026/p0_environment_lock.json`. The command records the current Conda explicit
list, pip freeze, installed distributions, interpreter identity, and a GPU snapshot. It does not
install, remove, or update packages. The prepared agent-model smoke runner remains unauthorized until
this lock and the completed Model B manifest have both been audited locally.

## LLM Judge exact-prompt smoke after Dense acceptance

The BGE Dense smoke passed and is locked in
`configs/paper_2026/dense_retrieval_v0_1.result.lock.json`. The remaining P0 model check is the
development-only exact-prompt smoke for the frozen Qwen3-8B applicability judge. Synchronize:

- `configs/paper_2026/llm_judge_v0_1.yaml`;
- `src/failure_memory/paper_2026/llm_judge.py`;
- `scripts/paper_2026/smoke_llm_judge.py`;
- the already existing `scripts/paper_2026/smoke_agent_model.py`.

From the repository root, run on one GPU with at least 20,000 MiB free:

```bash
CUDA_VISIBLE_DEVICES=0 \
/home/amax/miniconda3/envs/failure-memory-pilot/bin/python \
  scripts/paper_2026/smoke_llm_judge.py \
  --model-path /home/amax/PycharmProjects/AINegoProject/src/Models/LLM/Qwen3-8B \
  --manifest configs/proper_v1/qwen3_8b_model.sha256 \
  --physical-gpu-index 0 \
  --minimum-free-mib 20000 \
  --output outputs/paper_2026/p0_smoke_llm_judge_qwen3_8b.json
```

This smoke uses one synthetic timeout case and three synthetic memories. It does not read or produce
formal target selections. Return only
`outputs/paper_2026/p0_smoke_llm_judge_qwen3_8b.json` for local audit.
