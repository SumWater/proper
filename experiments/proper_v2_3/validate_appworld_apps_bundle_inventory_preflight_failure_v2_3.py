"""Freeze the returned AppWorld dependency preflight failure."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/proper_v2_3/appworld_apps_bundle_inventory_preflight_failure_freeze_v2_3.json"
SCHEMA = ROOT / "schemas/proper_v2_3/appworld_apps_bundle_inventory_preflight_failure_freeze.schema.json"
RUN_SCHEMA = ROOT / "schemas/proper_v2_3/appworld_apps_bundle_inventory.schema.json"
OUTPUT = ROOT / "outputs/proper_v2_3/appworld_apps_bundle_inventory_preflight_failure_freeze/validation.json"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    config, schema, run_schema = load(CONFIG), load(SCHEMA), load(RUN_SCHEMA)
    failed_run = config["failed_run"]
    result = load(ROOT / failed_run["result_path"])
    tests = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_proper_v2_3_appworld_apps_bundle_inventory_preflight_failure_freeze"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    failed_checks = [key for key, value in result["checks"].items() if not value]
    boundary = config["observed_boundary"]
    checks = {
        "returned_result_hash_matches": sha256(ROOT / failed_run["result_path"]) == failed_run["result_sha256"],
        "all_frozen_inputs_match": all(sha256(ROOT / item["path"]) == item["sha256"] for item in config["frozen_inputs"]),
        "dependency_checks_and_inventory_only_failed": failed_checks == config["failure_classification"]["failed_checks"],
        "missing_dependency_preceded_version_and_inventory": not result["checks"]["cryptography_dependency_available"] and not result["checks"]["cryptography_version_allowed"] and result["inventory"] is None,
        "revision_worktree_wheel_hash_and_boundary_checks_passed": all(result["checks"][key] for key in ("all_frozen_input_hashes_match", "project_revision_matches", "tracked_worktree_clean", "wheel_is_outside_tracked_project", "wheel_path_is_absolute", "zero_network_extract_model_boundary_closed")),
        "decryption_extraction_task_model_and_gpu_boundaries_closed": all(result[key] is expected for key, expected in boundary.items()),
        "five_freeze_tests_pass": tests.returncode == 0 and "Ran 5 tests" in tests.stderr,
        "retry_remains_closed_pending_separate_dependency_protocol": config["repair_gate"]["require_separate_dependency_provisioning_protocol"] and not config["repair_gate"]["retry_authorized_now"],
        "repair_requires_offline_or_hash_pinned_allowed_dependency": config["repair_gate"]["require_offline_or_hash_pinned_artifact"] and config["repair_gate"]["require_allowed_cryptography_major"],
        "scientific_method_and_claims_unchanged": not config["failure_classification"]["scientific_protocol_changed"] and not config["repair_gate"]["method_prompt_budget_model_task_or_endpoint_change_allowed"],
        "validation_schema_is_closed": schema["additionalProperties"] is False,
        "returned_result_matches_closed_run_shape": set(run_schema["required"]) <= set(result) <= set(run_schema["properties"]),
    }
    value: dict[str, Any] = {
        "schema_version": 1,
        "run_kind": "proper_v2_3_appworld_apps_bundle_inventory_preflight_failure_freeze",
        "passed": all(checks.values()),
        "checks": checks,
        "freeze_config_sha256": sha256(CONFIG),
        "result_sha256": sha256(ROOT / failed_run["result_path"]),
        "failed_project_revision": failed_run["project_revision"],
        "failed_result_preserved": True,
        "apps_bundle_decrypted": False,
        "source_extracted": False,
        "protected_plaintext_persisted": False,
        "task_or_api_data_read": False,
        "model_loaded": False,
        "gpu_used": False,
        "dependency_repair_design_authorized": all(checks.values()),
        "inventory_retry_authorized": False,
        "next_gate": "design_offline_cryptography_dependency_provisioning" if all(checks.values()) else "stop_and_preserve_preflight_failure",
    }
    required, allowed = set(schema["required"]), set(schema["properties"])
    value["checks"]["validation_matches_closed_schema_fields"] = required <= set(value) <= allowed
    value["passed"] = all(value["checks"].values())
    value["dependency_repair_design_authorized"] = value["passed"]
    value["next_gate"] = "design_offline_cryptography_dependency_provisioning" if value["passed"] else "stop_and_preserve_preflight_failure"
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes((json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0 if value["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
