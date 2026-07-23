#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

model_dir="/home/amax/PycharmProjects/AINegoProject/src/Models/LLM/Qwen3-8B"

sha256sum -c configs/project_source.sha256

CUDA_VISIBLE_DEVICES=0 \
HF_HUB_OFFLINE=1 \
TRANSFORMERS_OFFLINE=1 \
conda run --no-capture-output -n failure-memory-pilot \
  python experiments/confirmatory_transient_authz_v1.py \
  --run \
  --model "$model_dir" \
  --conda-lock work/lab_conda_explicit.lock \
  --pip-lock work/lab_pip_freeze.lock \
  --model-manifest configs/qwen3_8b_model.sha256 \
  --project-manifest configs/project_source.sha256
