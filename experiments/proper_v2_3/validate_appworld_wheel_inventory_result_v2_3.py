"""Freeze the returned read-only AppWorld wheel inventory."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/proper_v2_3/appworld_wheel_inventory_result_freeze_v2_3.json"
SCHEMA = ROOT / "schemas/proper_v2_3/appworld_wheel_inventory_result_freeze.schema.json"
REMOTE_SCHEMA = ROOT / "schemas/proper_v2_3/appworld_offline_wheel_inventory.schema.json"
OUTPUT = ROOT / "outputs/proper_v2_3/appworld_wheel_inventory_result_freeze/validation.json"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def validate() -> dict[str, Any]:
    config = load(CONFIG)
    schema = load(SCHEMA)
    remote_schema = load(REMOTE_SCHEMA)
    run = config["run"]
    result_path = ROOT / run["path"]
    result = load(result_path)
    inventory = result["inventory"]
    members = inventory["members"]
    paths = [item["relative_path"] for item in members]
    member_by_path = {item["relative_path"]: item for item in members}
    expected = config["expected_inventory"]
    tests = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_proper_v2_3_appworld_wheel_inventory_result_freeze"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    checks = {
        "remote_result_bytes_and_hash_match": result_path.stat().st_size == run["bytes"] and sha256(result_path) == run["sha256"],
        "all_frozen_input_hashes_match": all(sha256(ROOT / item["path"]) == item["sha256"] for item in config["frozen_inputs"]),
        "remote_result_matches_closed_top_level_schema": set(result) == set(remote_schema["required"]) == set(remote_schema["properties"]),
        "all_remote_checks_passed": result["passed"] and result["stop_reason"] is None and all(result["checks"].values()),
        "remote_project_revision_matches": result["project_revision"] == run["project_revision"] == result["expected_project_revision"],
        "wheel_identity_and_counts_match": all(inventory[key] == expected[key] for key in ("wheel_filename", "wheel_size_bytes", "wheel_sha256", "distribution", "version", "member_count", "total_uncompressed_bytes", "member_manifest_sha256")),
        "member_paths_are_sorted_unique_and_safe": paths == sorted(paths) and len(paths) == len(set(paths)) and not any(PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts or "\\" in path for path in paths),
        "member_count_total_and_manifest_recompute": len(members) == inventory["member_count"] and sum(item["uncompressed_bytes"] for item in members) == inventory["total_uncompressed_bytes"] and canonical_sha256(members) == inventory["member_manifest_sha256"],
        "two_encrypted_bundle_records_match": inventory["bundle_paths"] == [item["path"] for item in expected["bundles"]] and all(member_by_path[item["path"]]["uncompressed_bytes"] == item["uncompressed_bytes"] and member_by_path[item["path"]]["sha256"] == item["sha256"] for item in expected["bundles"]),
        "no_install_task_model_or_gpu_boundary_crossed": not any(result[key] for key in ("wheel_extracted", "protected_bundle_opened", "appworld_imported", "task_or_api_data_read", "model_loaded", "gpu_used")),
        "five_result_freeze_tests_pass": tests.returncode == 0 and "Ran 5 tests" in tests.stderr,
        "rerun_install_model_and_claim_gates_closed": not config["disposition"]["wheel_inventory_rerun_authorized"] and not config["disposition"]["source_install_authorized"] and not config["disposition"]["model_run_authorized"] and not config["disposition"]["confirmatory_claim_authorized"],
        "freeze_schema_is_closed": schema["additionalProperties"] is False and set(schema["required"]) == set(schema["properties"]),
    }
    value: dict[str, Any] = {
        "schema_version": 1,
        "run_kind": "proper_v2_3_appworld_wheel_inventory_result_freeze",
        "passed": False,
        "checks": checks,
        "freeze_config_sha256": sha256(CONFIG),
        "remote_result_sha256": sha256(result_path),
        "remote_project_revision": result["project_revision"],
        "member_count": inventory["member_count"],
        "bundle_count": inventory["bundle_count"],
        "member_manifest_sha256": inventory["member_manifest_sha256"],
        "wheel_extracted": False,
        "protected_bundle_opened": False,
        "appworld_imported": False,
        "task_or_api_data_read": False,
        "model_loaded": False,
        "gpu_used": False,
        "scientific_stage_passed": False,
        "wheel_inventory_rerun_authorized": False,
        "controlled_install_protocol_design_authorized": False,
        "source_install_authorized": False,
        "model_run_authorized": False,
        "confirmatory_claim_authorized": False,
        "next_gate": "design_controlled_install_and_static_api_inventory_protocol",
    }
    checks["freeze_value_matches_closed_schema_fields"] = set(value) == set(schema["required"])
    value["passed"] = all(checks.values())
    value["controlled_install_protocol_design_authorized"] = value["passed"]
    return value


def main() -> int:
    result = validate()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
