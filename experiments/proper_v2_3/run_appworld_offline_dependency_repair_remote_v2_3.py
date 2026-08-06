"""Provision pinned wheels offline, then invoke the frozen AppWorld inventory once."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/proper_v2_3/appworld_offline_dependency_repair_v2_3.json"
INVENTORY_RUNNER = ROOT / "experiments/proper_v2_3/run_appworld_apps_bundle_inventory_remote_v2_3.py"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-c", "core.fileMode=false", *args], cwd=ROOT,
        check=True, capture_output=True, text=True,
    ).stdout.strip()


def outside_project(path: Path) -> bool:
    try:
        path.relative_to(ROOT)
    except ValueError:
        return True
    return False


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes((json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    temporary.replace(path)


def run(expected_revision: str, wheelhouse: Path, target: Path, appworld_wheel: Path, output_dir: Path) -> dict[str, Any]:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    wheelhouse, target, appworld_wheel = wheelhouse.resolve(), target.resolve(), appworld_wheel.resolve()
    revision = git("rev-parse", "HEAD")
    tracked = git("status", "--short", "--untracked-files=no")
    artifact_paths = [wheelhouse / item["filename"] for item in config["artifacts"]]
    observed_files = sorted(path.name for path in wheelhouse.iterdir() if path.is_file()) if wheelhouse.is_dir() else []
    expected_files = sorted(item["filename"] for item in config["artifacts"])
    artifacts_match = wheelhouse.is_dir() and observed_files == expected_files and all(
        path.is_file() and path.stat().st_size == item["bytes"] and sha256(path) == item["sha256"]
        for path, item in zip(artifact_paths, config["artifacts"])
    )
    checks = {
        "project_revision_matches": revision == expected_revision,
        "tracked_worktree_clean": tracked == "",
        "python_311": sys.version_info[:2] == (3, 11),
        "linux_x86_64": sys.platform.startswith("linux") and platform.machine().lower() in {"x86_64", "amd64"},
        "wheelhouse_is_absolute_external": wheelhouse.is_absolute() and outside_project(wheelhouse),
        "target_is_absolute_external_and_absent": target.is_absolute() and outside_project(target) and not target.exists(),
        "appworld_wheel_is_absolute_external": appworld_wheel.is_absolute() and outside_project(appworld_wheel),
        "all_pinned_artifacts_match": artifacts_match,
        "frozen_inputs_match": all(sha256(ROOT / item["path"]) == item["sha256"] for item in config["frozen_inputs"]),
    }
    status = "preflight_failed"
    stop_reason: str | None = "preflight_failed"
    provision_attempted = False
    provision_returncode: int | None = None
    probe: dict[str, str] | None = None
    inventory_returncode: int | None = None
    inventory_path = output_dir / "inventory.json"
    if all(checks.values()):
        provision_attempted = True
        command = [
            sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
            "--no-index", "--no-deps", "--only-binary=:all:", "--target", str(target),
            *[str(path) for path in artifact_paths],
        ]
        installed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
        provision_returncode = installed.returncode
        if installed.returncode != 0:
            status, stop_reason = "provision_failed", "offline_pip_failed"
        else:
            env = os.environ.copy()
            env["PYTHONPATH"] = str(target) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
            probe_code = "import json,importlib.metadata as m; print(json.dumps({k:m.version(k) for k in ('cryptography','cffi','pycparser')},sort_keys=True))"
            probed = subprocess.run([sys.executable, "-c", probe_code], cwd=ROOT, env=env, capture_output=True, text=True, check=False)
            try:
                probe = json.loads(probed.stdout.strip()) if probed.returncode == 0 else None
            except json.JSONDecodeError:
                probe = None
            expected_versions = config["expected_versions"]
            if probe != expected_versions:
                status, stop_reason = "probe_failed", "installed_versions_or_imports_mismatch"
            else:
                invoked = subprocess.run(
                    [sys.executable, str(INVENTORY_RUNNER), "--expected-project-revision", expected_revision,
                     "--wheel", str(appworld_wheel), "--output", str(inventory_path)],
                    cwd=ROOT, env=env, capture_output=True, text=True, check=False,
                )
                inventory_returncode = invoked.returncode
                if invoked.returncode == 0:
                    status, stop_reason = "inventory_completed", None
                else:
                    status, stop_reason = "inventory_stopped", "guarded_inventory_failed"
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_3_appworld_offline_dependency_repair",
        "project_revision": revision,
        "expected_project_revision": expected_revision,
        "checks": checks,
        "status": status,
        "stop_reason": stop_reason,
        "provision_attempted": provision_attempted,
        "provision_returncode": provision_returncode,
        "installed_versions": probe,
        "inventory_returncode": inventory_returncode,
        "inventory_path": str(inventory_path) if inventory_path.exists() else None,
        "network_allowed": False,
        "protected_plaintext_persisted": False,
        "source_extracted": False,
        "task_or_api_data_read": False,
        "model_loaded": False,
        "gpu_used": False,
        "next_gate": "freeze_returned_apps_bundle_inventory" if status == "inventory_completed" else "stop_and_preserve_dependency_repair_result",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-project-revision", required=True)
    parser.add_argument("--wheelhouse", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--appworld-wheel", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = args.output_dir or ROOT / "outputs/proper_v2_3/appworld_dependency_repair_remote" / f"{stamp}-{socket.gethostname().split('.')[0]}-{args.expected_project_revision[:12]}"
    result = run(args.expected_project_revision, args.wheelhouse, args.target, args.appworld_wheel, output_dir)
    write_json_atomic(output_dir / "provisioning.json", result)
    print(json.dumps({"output": str(output_dir), "status": result["status"], "inventory_path": result["inventory_path"], "model_loaded": False, "gpu_used": False}, sort_keys=True))
    return 0 if result["status"] == "inventory_completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
