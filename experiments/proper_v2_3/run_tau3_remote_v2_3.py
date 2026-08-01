"""Cross-platform one-command bootstrap for the remote tau3 CPU screen."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs" / "proper_v2_3" / "tau3_remote_execution_v2_3.yaml"


def load_config() -> dict[str, Any]:
    value = json.loads(CONFIG.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("remote execution contract must be a JSON object")
    return value


def run_checked(command: list[str], *, directory: Path = ROOT) -> str:
    completed = subprocess.run(
        command, cwd=directory, check=True, capture_output=True, text=True, encoding="utf-8"
    )
    return completed.stdout.strip()


def environment_python(environment_directory: Path) -> Path:
    if os.name == "nt":
        return environment_directory / "Scripts" / "python.exe"
    return environment_directory / "bin" / "python"


def prepare_tau(config: dict[str, Any]) -> None:
    tau = config["tau_source"]
    directory = ROOT / tau["directory"]
    if not directory.is_dir():
        directory.parent.mkdir(parents=True, exist_ok=True)
        run_checked([
            "git", "clone", "--branch", tau["tag"], "--depth", "1",
            tau["repository"], str(directory),
        ])
    actual = run_checked(["git", "-C", str(directory), "rev-parse", "HEAD"])
    if actual != tau["revision"]:
        raise RuntimeError(f"tau source revision mismatch: expected {tau['revision']}, got {actual}")


def prepare_environment(config: dict[str, Any]) -> Path:
    required = config["python"]
    if (
        sys.version_info.major != required["required_major"]
        or sys.version_info.minor not in required["allowed_minors"]
    ):
        allowed = ", ".join(
            f"{required['required_major']}.{minor}" for minor in required["allowed_minors"]
        )
        raise RuntimeError(f"Python {allowed} is required, got {sys.version.split()[0]}")
    work = ROOT / "work"
    work.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="proper_v2_3_tau3_remote_venv_", dir=work))
    python = environment_python(directory)
    subprocess.run([sys.executable, "-m", "venv", str(directory)], cwd=ROOT, check=True)
    subprocess.run([
        str(python), "-m", "pip", "install", "--disable-pip-version-check", "--no-input",
        "--requirement", str(ROOT / required["requirements_file"]),
    ], cwd=ROOT, check=True)
    return python


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-project-revision", required=True)
    args = parser.parse_args()
    config = load_config()
    prepare_tau(config)
    python = prepare_environment(config)
    environment = dict(os.environ)
    environment["PROPER_V2_3_EXECUTION_ROLE"] = config["execution_role"]
    environment["CUDA_VISIBLE_DEVICES"] = config["runtime_guards"]["cuda_visible_devices"]
    environment["TOKENIZERS_PARALLELISM"] = "false"
    completed = subprocess.run([
        str(python), str(ROOT / "experiments" / "proper_v2_3" / "tau3_remote_execution_v2_3.py"),
        "--expected-project-revision", args.expected_project_revision,
    ], cwd=ROOT, env=environment, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
