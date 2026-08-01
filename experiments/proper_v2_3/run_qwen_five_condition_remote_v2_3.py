"""One-shot remote launcher for the frozen v2.3 Qwen development run."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "experiments/proper_v2_3/toolsandbox_qwen_five_condition_development_v2_3.py"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-project-revision", required=True)
    args = parser.parse_args()
    environment = dict(os.environ)
    environment["PROPER_V2_3_EXECUTION_ROLE"] = "proper_v2_3_qwen_five_condition_remote_development"
    environment["CUDA_VISIBLE_DEVICES"] = "0"
    environment["TOKENIZERS_PARALLELISM"] = "false"
    preflight = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p",
         "test_toolsandbox_v2_3_qwen_runner.py", "-v"],
        cwd=ROOT, env={**environment, "CUDA_VISIBLE_DEVICES": "-1"}, check=False,
    )
    if preflight.returncode != 0:
        return preflight.returncode
    completed = subprocess.run(
        [sys.executable, str(RUNNER), "--expected-project-revision", args.expected_project_revision],
        cwd=ROOT, env=environment, check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
