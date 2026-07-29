#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

model_dir="${1:-/home/amax/PycharmProjects/AINegoProject/src/Models/LLM/Qwen3-8B}"
test_file="work/toolmisusebench_test/test_public.jsonl"
expected_test_sha="12c5e1e93926f4089dfc8d0c60cea53b556057360562375510744858fc6f1161"

test -f "$test_file"
test "$(stat -c '%s' "$test_file")" = "1695141"
test "$(sha256sum "$test_file" | awk '{print $1}')" = "$expected_test_sha"
test -f work/lab_conda_explicit.lock
test -f work/lab_pip_freeze.lock
test -d "$model_dir"

sha256sum -c configs/proper_v1/project_source.sha256

conda run --no-capture-output -n failure-memory-pilot \
  python experiments/proper_v1/confirmatory_gate_v1.py --prepare

conda run --no-capture-output -n failure-memory-pilot \
  python experiments/proper_v1/confirmatory_gate_v1.py --cpu-dry-run

CUDA_VISIBLE_DEVICES=0 \
HF_HUB_OFFLINE=1 \
TRANSFORMERS_OFFLINE=1 \
conda run --no-capture-output -n failure-memory-pilot \
  python experiments/proper_v1/confirmatory_gate_v1.py \
  --run \
  --model "$model_dir" \
  --conda-lock work/lab_conda_explicit.lock \
  --pip-lock work/lab_pip_freeze.lock \
  --model-manifest configs/proper_v1/qwen3_8b_model.sha256 \
  --project-manifest configs/proper_v1/project_source.sha256
