"""Cross-platform CPU bootstrap for five-condition preparation validation."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS = ROOT / "experiments" / "proper_v2_3"

from run_tau3_remote_v2_3 import (  # noqa: E402
    load_config as load_environment_config,
    prepare_environment,
    prepare_tau,
)
from prepare_five_condition_development_v2_3 import load_object  # noqa: E402

FIVE_CONDITION_CONFIG = ROOT / "configs" / "proper_v2_3" / "five_condition_development_v2_3.yaml"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-project-revision", required=True)
    args = parser.parse_args()
    environment_config = load_environment_config()
    config = load_object(FIVE_CONDITION_CONFIG)
    prepare_tau(environment_config)
    python = prepare_environment(environment_config)
    environment = dict(os.environ)
    policy = config["remote_preparation_validation"]
    environment["PROPER_V2_3_EXECUTION_ROLE"] = policy["execution_role"]
    environment["CUDA_VISIBLE_DEVICES"] = policy["cuda_visible_devices"]
    environment["TOKENIZERS_PARALLELISM"] = "false"
    completed = subprocess.run([
        str(python), str(EXPERIMENTS / "validate_five_condition_protocol_v2_3.py"),
        "--expected-project-revision", args.expected_project_revision,
    ], cwd=ROOT, env=environment, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
