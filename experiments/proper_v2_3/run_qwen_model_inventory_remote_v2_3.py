"""One-shot remote read-only inventory of the frozen local Qwen directory."""

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
CONFIG = ROOT / "configs/proper_v2_3/qwen_model_inventory_v2_3.json"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.failure_memory.proper_v2.v2_3.model_inventory import inventory_regular_files


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-c", "core.fileMode=false", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(expected_project_revision: str) -> dict[str, Any]:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    project_revision = _git("rev-parse", "HEAD")
    tracked_status = _git("status", "--porcelain", "--untracked-files=no")
    python_ok = (
        sys.version_info.major == config["allowed_python"]["major"]
        and sys.version_info.minor in config["allowed_python"]["minors"]
    )
    boundary = config["boundary"]
    checks = {
        "project_revision_matches": project_revision == expected_project_revision,
        "tracked_worktree_clean": tracked_status == "",
        "python_version_allowed": python_ok,
        "read_only_boundary_closed": boundary["read_file_bytes_only"] and not any(
            (
                boundary["import_model_libraries"],
                boundary["load_model"],
                boundary["read_model_outputs"],
                boundary["execute_tau_task"],
                boundary["use_gpu"],
            )
        ),
    }
    inventory: dict[str, Any] = {
        "files": [], "file_count": 0, "total_bytes": 0, "manifest_sha256": None
    }
    stop_reason: str | None = None
    if not all(checks.values()):
        stop_reason = "preflight_failed"
    else:
        try:
            inventory = inventory_regular_files(
                Path(config["model_root"]),
                chunk_bytes=config["hash_contract"]["chunk_bytes"],
            )
        except (OSError, ValueError) as exc:
            stop_reason = f"inventory_failed:{type(exc).__name__}:{exc}"
    checks["inventory_completed"] = stop_reason is None
    passed = all(checks.values())
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_3_remote_read_only_qwen_model_inventory",
        "project_revision": project_revision,
        "expected_project_revision": expected_project_revision,
        "config_sha256": _sha256(CONFIG),
        "model_root": config["model_root"],
        "checks": checks,
        "passed": passed,
        "stop_reason": stop_reason,
        **inventory,
        "model_loaded": False,
        "model_outputs_read": False,
        "task_executed": False,
        "gpu_used": False,
        "acquisition_runtime_freeze_authorized": False,
        "real_branch_capture_authorized": False,
        "model_runner_authorized": False,
        "confirmatory_run_authorized": False,
        "next_gate": "sync_and_freeze_remote_model_inventory" if passed else "stop_model_inventory",
    }


def _default_output(revision: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    host = socket.gethostname().split(".")[0]
    return ROOT / "outputs/proper_v2_3/qwen_model_inventory_remote" / f"{stamp}-{host}-{revision[:12]}" / "inventory.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-project-revision", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or _default_output(args.expected_project_revision)
    result = run(args.expected_project_revision)
    output.parent.mkdir(parents=True, exist_ok=False)
    output.write_bytes((json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps({
        "output": str(output), "passed": result["passed"],
        "file_count": result["file_count"], "total_bytes": result["total_bytes"],
        "manifest_sha256": result["manifest_sha256"],
        "model_loaded": False, "gpu_used": False,
    }, ensure_ascii=False, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
