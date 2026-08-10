from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def run(args: list[str], timeout: int = 180) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return {
            "ok": False,
            "args": args,
            "returncode": None,
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc}",
        }
    return {
        "ok": completed.returncode == 0,
        "args": args,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def find_conda() -> Path | None:
    candidates = []
    if os.environ.get("CONDA_EXE"):
        candidates.append(Path(os.environ["CONDA_EXE"]))
    prefix = Path(sys.prefix).resolve()
    if len(prefix.parents) >= 2:
        candidates.append(prefix.parents[1] / "bin" / "conda")
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


def normalized_lines(value: str) -> list[str]:
    return sorted(line.rstrip() for line in value.splitlines() if line.strip())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture a read-only remote environment lock for paper experiments."
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-prefix", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    actual_prefix = Path(sys.prefix).resolve()
    expected_prefix = args.expected_prefix.expanduser().resolve() if args.expected_prefix else None
    prefix_matches = expected_prefix is None or actual_prefix == expected_prefix

    pip_result = run([sys.executable, "-m", "pip", "freeze", "--all"])
    conda = find_conda()
    conda_result = (
        run([str(conda), "list", "--explicit", "--prefix", str(actual_prefix)])
        if conda is not None
        else {
            "ok": False,
            "args": [],
            "returncode": None,
            "stdout": "",
            "stderr": "conda executable not found",
        }
    )
    gpu_result = run(
        [
            "nvidia-smi",
            "--query-gpu=index,name,uuid,memory.total,memory.free,driver_version",
            "--format=csv,noheader,nounits",
        ]
    )
    distributions = sorted(
        {
            f"{dist.metadata['Name']}=={dist.version}"
            for dist in importlib.metadata.distributions()
            if dist.metadata.get("Name")
        },
        key=str.casefold,
    )
    pip_lines = normalized_lines(pip_result["stdout"])
    conda_lines = [line.rstrip() for line in conda_result["stdout"].splitlines() if line.strip()]
    payload = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "read_only_capture": True,
        "hostname": platform.node(),
        "platform": platform.platform(),
        "python": {
            "executable": sys.executable,
            "version": platform.python_version(),
            "prefix": str(actual_prefix),
            "expected_prefix": str(expected_prefix) if expected_prefix else None,
            "prefix_matches": prefix_matches,
        },
        "selected_environment_variables": {
            "CONDA_DEFAULT_ENV": os.environ.get("CONDA_DEFAULT_ENV"),
            "CONDA_PREFIX": os.environ.get("CONDA_PREFIX"),
            "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES"),
        },
        "installed_distributions": distributions,
        "installed_distributions_sha256": sha256_text("\n".join(distributions) + "\n"),
        "pip_freeze": {
            **pip_result,
            "normalized_lines": pip_lines,
            "normalized_sha256": sha256_text("\n".join(pip_lines) + "\n"),
        },
        "conda_explicit": {
            **conda_result,
            "conda_executable": str(conda) if conda else None,
            "lines": conda_lines,
            "sha256": sha256_text("\n".join(conda_lines) + "\n"),
        },
        "gpu_snapshot": gpu_result,
    }
    payload["capture_passed"] = bool(
        prefix_matches and pip_result["ok"] and conda_result["ok"] and gpu_result["ok"]
    )
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)
    return 0 if payload["capture_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
