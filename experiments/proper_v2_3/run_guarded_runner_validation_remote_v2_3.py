"""One-command CPU entry point for remote guarded-runner validation."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "experiments" / "proper_v2_3" / "validate_guarded_runner_v2_3.py"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-project-revision", required=True)
    args = parser.parse_args()
    environment = dict(os.environ)
    environment["PROPER_V2_3_EXECUTION_ROLE"] = (
        "proper_v2_3_guarded_runner_remote_cpu_validation"
    )
    environment["CUDA_VISIBLE_DEVICES"] = "-1"
    environment["TOKENIZERS_PARALLELISM"] = "false"
    completed = subprocess.run(
        [sys.executable, str(VALIDATOR),
         "--expected-project-revision", args.expected_project_revision],
        cwd=ROOT, env=environment, check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
