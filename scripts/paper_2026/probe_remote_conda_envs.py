from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROBE_CODE = r'''
import importlib
import json
import platform
import sys

names = ("torch", "transformers", "accelerate", "bitsandbytes", "sentence_transformers", "sklearn")
result = {
    "python_version": sys.version,
    "python_executable": sys.executable,
    "platform": platform.platform(),
    "imports": {},
}
for name in names:
    try:
        module = importlib.import_module(name)
    except Exception as exc:
        result["imports"][name] = {
            "imported": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
        continue
    record = {
        "imported": True,
        "version": getattr(module, "__version__", None),
        "file": getattr(module, "__file__", None),
    }
    if name == "torch":
        record["cuda_version"] = getattr(getattr(module, "version", None), "cuda", None)
        record["cuda_available"] = bool(module.cuda.is_available())
        record["cuda_device_count"] = int(module.cuda.device_count())
        if module.cuda.is_available():
            record["bf16_supported"] = bool(module.cuda.is_bf16_supported())
    result["imports"][name] = record
print(json.dumps(result, ensure_ascii=True, sort_keys=True))
'''


def run(args: list[str], timeout: int = 120) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "error": f"{type(exc).__name__}: {exc}"}
    return {
        "available": True,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def conda_environment_prefixes() -> dict[str, Path]:
    response = run(["conda", "env", "list", "--json"])
    if not response.get("available") or response.get("returncode") != 0:
        raise RuntimeError(f"cannot list conda environments: {response}")
    payload = json.loads(str(response["stdout"]))
    prefixes = [Path(item).expanduser().resolve() for item in payload.get("envs", [])]
    return {prefix.name: prefix for prefix in prefixes}


def probe_environment(name: str, prefix: Path) -> dict[str, Any]:
    python = prefix / "bin" / "python"
    record: dict[str, Any] = {"name": name, "prefix": str(prefix), "python": str(python)}
    if not python.is_file():
        record["probe"] = {"available": False, "error": "missing_python"}
        return record
    response = run([str(python), "-c", PROBE_CODE])
    record["probe"] = response
    if response.get("returncode") == 0:
        try:
            record["result"] = json.loads(str(response["stdout"]).splitlines()[-1])
        except (IndexError, json.JSONDecodeError) as exc:
            record["parse_error"] = f"{type(exc).__name__}: {exc}"
    return record


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe existing Conda environments without installing packages or loading models."
    )
    parser.add_argument(
        "--env",
        action="append",
        default=[],
        help="Conda environment name to probe; may be repeated. Defaults to all environments.",
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    prefixes = conda_environment_prefixes()
    selected = args.env or sorted(prefixes)
    missing = [name for name in selected if name not in prefixes]
    if missing:
        raise ValueError(f"unknown Conda environments: {missing}")
    payload = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "boundary": {
            "packages_installed": False,
            "environment_mutated": False,
            "weights_loaded": False,
            "model_inference_run": False,
        },
        "requested_environments": selected,
        "environments": [probe_environment(name, prefixes[name]) for name in selected],
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        sys.stdout.write(rendered)
    else:
        output = args.output.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

