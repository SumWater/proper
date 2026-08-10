from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


GB = 1_000_000_000


def nearest_existing(path: Path) -> Path:
    candidate = path.expanduser()
    while not candidate.exists():
        parent = candidate.parent
        if parent == candidate:
            raise FileNotFoundError(f"No existing parent found for {path}")
        candidate = parent
    return candidate.resolve()


def disk_record(label: str, requested_path: Path) -> dict[str, Any]:
    probe_path = nearest_existing(requested_path)
    usage = shutil.disk_usage(probe_path)
    return {
        "label": label,
        "requested_path": str(requested_path),
        "probed_existing_path": str(probe_path),
        "device_id": os.stat(probe_path).st_dev,
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
        "total_gb_decimal": round(usage.total / GB, 2),
        "used_gb_decimal": round(usage.used / GB, 2),
        "free_gb_decimal": round(usage.free / GB, 2),
    }


def directory_size(path: Path) -> dict[str, Any]:
    expanded = path.expanduser()
    if not expanded.exists():
        return {"path": str(expanded), "exists": False, "size_bytes": None}
    try:
        completed = subprocess.run(
            ["du", "-sb", str(expanded)],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return {
            "path": str(expanded.resolve()),
            "exists": True,
            "size_bytes": None,
            "error": f"{type(exc).__name__}: {exc}",
        }
    if completed.returncode != 0:
        return {
            "path": str(expanded.resolve()),
            "exists": True,
            "size_bytes": None,
            "error": completed.stderr.strip(),
        }
    size_bytes = int(completed.stdout.split()[0])
    return {
        "path": str(expanded.resolve()),
        "exists": True,
        "size_bytes": size_bytes,
        "size_gb_decimal": round(size_bytes / GB, 2),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only storage gate before downloading paper model B."
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=Path(
            "/home/amax/PycharmProjects/AINegoProject/src/Models/LLM/"
            "Mistral-7B-Instruct-v0.3"
        ),
    )
    parser.add_argument(
        "--project-dir",
        type=Path,
        default=Path("/home/amax/PycharmProjects/AINegoProject"),
    )
    parser.add_argument(
        "--hf-cache",
        type=Path,
        default=Path("/home/amax/.cache/huggingface"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    locations = [
        disk_record("model_target", args.model_dir),
        disk_record("project", args.project_dir),
        disk_record("huggingface_cache", args.hf_cache),
    ]
    model_free = locations[0]["free_bytes"]
    expected_download = int(14.6 * GB)
    hard_minimum = 25 * GB
    recommended = 35 * GB
    payload = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "hostname": platform.node(),
        "read_only_probe": True,
        "download_not_started": True,
        "requirements": {
            "expected_filtered_download_bytes": expected_download,
            "expected_filtered_download_gb_decimal": 14.6,
            "hard_minimum_free_bytes": hard_minimum,
            "hard_minimum_free_gb_decimal": 25.0,
            "recommended_free_bytes": recommended,
            "recommended_free_gb_decimal": 35.0,
        },
        "filesystems": locations,
        "same_filesystem": {
            "model_and_project": locations[0]["device_id"] == locations[1]["device_id"],
            "model_and_hf_cache": locations[0]["device_id"] == locations[2]["device_id"],
        },
        "directory_sizes": [
            directory_size(args.model_dir.parent),
            directory_size(args.project_dir),
            directory_size(args.hf_cache),
        ],
        "gate": {
            "hard_minimum_pass": model_free >= hard_minimum,
            "recommended_headroom_pass": model_free >= recommended,
            "decision": (
                "pass"
                if model_free >= recommended
                else "conditional" if model_free >= hard_minimum else "fail"
            ),
        },
    }
    output = args.output.expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
