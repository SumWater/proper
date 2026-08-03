"""Read-only remote inventory for one externally supplied pinned wheel."""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/proper_v2_3/appworld_offline_wheel_inventory_v2_3.json"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.failure_memory.proper_v2.v2_3.offline_wheel_inventory import inventory_wheel


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-c", "core.fileMode=false", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=False)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes((json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    temporary.replace(path)


def run(expected_project_revision: str, wheel_path: Path) -> dict[str, Any]:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    release = config["official_release_metadata"]
    revision = git("rev-parse", "HEAD")
    resolved_wheel = wheel_path.resolve(strict=False)
    try:
        resolved_wheel.relative_to(ROOT.resolve())
        wheel_outside_project = False
    except ValueError:
        wheel_outside_project = True
    checks = {
        "project_revision_matches": revision == expected_project_revision,
        "tracked_worktree_clean": git("status", "--porcelain", "--untracked-files=no") == "",
        "wheel_path_is_absolute": wheel_path.is_absolute(),
        "wheel_is_outside_tracked_project": wheel_outside_project,
        "read_only_boundary_closed": (
            not config["input_contract"]["network_download_by_inventory_runner"]
            and not config["input_contract"]["package_installation"]
            and not config["input_contract"]["wheel_extraction"]
            and not config["input_contract"]["protected_bundle_decryption"]
        ),
    }
    inventory: dict[str, Any] | None = None
    stop_reason: str | None = None
    if not all(checks.values()):
        stop_reason = "preflight_failed"
    else:
        try:
            inventory = inventory_wheel(
                wheel_path,
                expected_filename=release["filename"],
                expected_size_bytes=release["size_bytes"],
                expected_sha256=release["sha256"],
                expected_distribution=release["distribution"],
                expected_version=release["version"],
                limits=config["zip_safety_limits"],
            )
        except (OSError, ValueError) as exc:
            stop_reason = f"inventory_failed:{type(exc).__name__}:{exc}"
    checks["inventory_completed"] = inventory is not None and stop_reason is None
    passed = all(checks.values())
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_3_appworld_read_only_offline_wheel_inventory",
        "project_revision": revision,
        "expected_project_revision": expected_project_revision,
        "config_sha256": sha256(CONFIG),
        "wheel_path": str(resolved_wheel),
        "checks": checks,
        "passed": passed,
        "stop_reason": stop_reason,
        "inventory": inventory,
        "wheel_extracted": False,
        "protected_bundle_opened": False,
        "appworld_imported": False,
        "task_or_api_data_read": False,
        "model_loaded": False,
        "gpu_used": False,
        "source_install_authorized": False,
        "next_gate": "freeze_returned_wheel_inventory" if passed else "stop_wheel_inventory",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-project-revision", required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    host = socket.gethostname().split(".")[0]
    output = args.output or ROOT / "outputs/proper_v2_3/appworld_wheel_inventory_remote" / f"{stamp}-{host}-{args.expected_project_revision[:12]}" / "inventory.json"
    result = run(args.expected_project_revision, args.wheel)
    write_json_atomic(output, result)
    print(json.dumps({
        "output": str(output),
        "passed": result["passed"],
        "stop_reason": result["stop_reason"],
        "member_count": result["inventory"]["member_count"] if result["inventory"] else 0,
        "bundle_count": result["inventory"]["bundle_count"] if result["inventory"] else 0,
        "model_loaded": False,
        "gpu_used": False,
    }, ensure_ascii=False, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
