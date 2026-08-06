"""One-shot aggregate-only inventory of the exact AppWorld apps bundle."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import importlib.metadata
import json
import socket
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/proper_v2_3/appworld_apps_bundle_inventory_implementation_v2_3.json"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.failure_memory.proper_v2.v2_3.encrypted_bundle_inventory import inventory_encrypted_bundle
from src.failure_memory.proper_v2.v2_3.offline_wheel_inventory import file_sha256


def git(*args: str) -> str:
    return subprocess.run(["git", "-c", "core.fileMode=false", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=False)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes((json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    temporary.replace(path)


def run(expected_project_revision: str, wheel_path: Path) -> dict[str, Any]:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    revision = git("rev-parse", "HEAD")
    resolved_wheel = wheel_path.resolve(strict=False)
    try:
        resolved_wheel.relative_to(ROOT.resolve())
        outside_project = False
    except ValueError:
        outside_project = True
    checks = {
        "project_revision_matches": revision == expected_project_revision,
        "tracked_worktree_clean": git("status", "--porcelain", "--untracked-files=no") == "",
        "wheel_path_is_absolute": wheel_path.is_absolute(),
        "wheel_is_outside_tracked_project": outside_project,
        "cryptography_dependency_available": importlib.util.find_spec("cryptography") is not None,
        "all_frozen_input_hashes_match": all(sha256(ROOT / item["path"]) == item["sha256"] for item in config["frozen_inputs"]),
        "zero_network_extract_model_boundary_closed": all(config["boundary"][key] is False for key in ("network_access", "source_extraction", "tests_bundle_read", "data_download", "task_or_api_data_read", "model_load", "gpu_use")),
    }
    if checks["cryptography_dependency_available"]:
        try:
            crypto_major = int(importlib.metadata.version("cryptography").split(".", 1)[0])
            checks["cryptography_version_allowed"] = crypto_major in config["allowed_cryptography_major_versions"]
        except (ValueError, importlib.metadata.PackageNotFoundError):
            checks["cryptography_version_allowed"] = False
    else:
        checks["cryptography_version_allowed"] = False
    inventory: dict[str, Any] | None = None
    stop_reason: str | None = None
    apps_bundle_decrypted = False
    if not all(checks.values()):
        stop_reason = "preflight_failed"
    else:
        try:
            wheel = config["wheel"]
            if resolved_wheel.name != wheel["filename"] or resolved_wheel.stat().st_size != wheel["bytes"] or file_sha256(resolved_wheel) != wheel["sha256"]:
                raise ValueError("wheel identity mismatch")
            bundle = config["apps_bundle"]
            with zipfile.ZipFile(resolved_wheel, "r") as archive:
                encrypted = archive.read(bundle["wheel_member_path"])
            if len(encrypted) != bundle["encrypted_bytes"] or hashlib.sha256(encrypted).hexdigest() != bundle["encrypted_sha256"]:
                raise ValueError("apps bundle identity mismatch")
            # From this point the inventory call necessarily attempts in-memory
            # decryption.  Record that boundary even if ZIP safety validation
            # subsequently rejects the decrypted payload.
            apps_bundle_decrypted = True
            inventory = inventory_encrypted_bundle(
                encrypted,
                expected_encrypted_bytes=bundle["encrypted_bytes"],
                expected_encrypted_sha256=bundle["encrypted_sha256"],
                password=config["public_crypto_material"]["password"],
                salt=config["public_crypto_material"]["salt_utf8"].encode("utf-8"),
                iterations=config["public_crypto_material"]["iterations"],
                limits=config["zip_safety_limits"],
            )
        except (OSError, KeyError, ValueError, zipfile.BadZipFile) as exc:
            stop_reason = f"inventory_failed:{type(exc).__name__}:{exc}"
    checks["inventory_completed"] = inventory is not None and stop_reason is None
    passed = all(checks.values())
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_3_appworld_aggregate_only_apps_bundle_inventory",
        "project_revision": revision,
        "expected_project_revision": expected_project_revision,
        "implementation_config_sha256": sha256(CONFIG),
        "wheel_path": str(resolved_wheel),
        "checks": checks,
        "passed": passed,
        "stop_reason": stop_reason,
        "inventory": inventory,
        "apps_bundle_decrypted": apps_bundle_decrypted,
        "tests_bundle_read": False,
        "tests_bundle_decrypted": False,
        "data_downloaded": False,
        "source_extracted": False,
        "protected_plaintext_persisted": False,
        "task_or_api_data_read": False,
        "model_loaded": False,
        "gpu_used": False,
        "static_api_inventory_authorized": False,
        "next_gate": "freeze_returned_apps_bundle_inventory" if passed else "stop_apps_bundle_inventory",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-project-revision", required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    host = socket.gethostname().split(".")[0]
    output = args.output or ROOT / "outputs/proper_v2_3/appworld_apps_bundle_inventory_remote" / f"{stamp}-{host}-{args.expected_project_revision[:12]}" / "inventory.json"
    result = run(args.expected_project_revision, args.wheel)
    write_json_atomic(output, result)
    print(json.dumps({"output":str(output),"passed":result["passed"],"stop_reason":result["stop_reason"],"member_count":result["inventory"]["member_count"] if result["inventory"] else 0,"apps_bundle_decrypted":result["apps_bundle_decrypted"],"source_extracted":False,"model_loaded":False,"gpu_used":False},ensure_ascii=False,sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
