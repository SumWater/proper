#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

sha256sum -c configs/proper_v1/project_source.sha256

conda run --no-capture-output -n failure-memory-pilot \
  python experiments/proper_v1/confirmatory_transient_authz_v1.py --cpu-dry-run

conda run --no-capture-output -n failure-memory-pilot \
  python experiments/proper_v1/confirmatory_transient_authz_v1.py --prepare
