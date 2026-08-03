"""CPU-only validation before one pinned AppWorld wheel inventory."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/proper_v2_3/appworld_offline_wheel_inventory_v2_3.json"
SCHEMA = ROOT / "schemas/proper_v2_3/appworld_offline_wheel_inventory.schema.json"
PREPARATION_SCHEMA = ROOT / "schemas/proper_v2_3/appworld_offline_wheel_inventory_preparation.schema.json"
RUNNER = ROOT / "experiments/proper_v2_3/run_appworld_offline_wheel_inventory_remote_v2_3.py"
INVENTORY = ROOT / "src/failure_memory/proper_v2/v2_3/offline_wheel_inventory.py"
OUTPUT = ROOT / "outputs/proper_v2_3/appworld_offline_wheel_inventory_preparation/validation.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate() -> dict[str, Any]:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    preparation_schema = json.loads(PREPARATION_SCHEMA.read_text(encoding="utf-8"))
    release = config["official_release_metadata"]
    boundary = config["boundary"]
    runner_source = RUNNER.read_text(encoding="utf-8")
    inventory_source = INVENTORY.read_text(encoding="utf-8")
    ast.parse(runner_source)
    ast.parse(inventory_source)
    tests = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_proper_v2_3_appworld_offline_wheel_inventory"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    checks = {
        "prior_source_design_hashes_match": all(sha256(ROOT / item["path"]) == item["sha256"] for item in config["frozen_inputs"]),
        "official_release_is_exactly_pinned": (
            release["distribution"] == "appworld"
            and release["version"] == "0.1.3.post1"
            and release["filename"] == "appworld-0.1.3.post1-py3-none-any.whl"
            and release["size_bytes"] == 625317
            and release["sha256"] == "db77f8003982502383a50fa2974983894bd1c54f64e2fd3f7e1540d5edd037eb"
            and release["download_url"].startswith("https://files.pythonhosted.org/")
        ),
        "inventory_has_no_network_install_extract_or_decrypt": all(
            config["input_contract"][key] is False
            for key in ("network_download_by_inventory_runner", "dependency_resolution", "package_installation", "appworld_install_command", "appworld_download_data_command", "wheel_extraction", "protected_bundle_decryption")
        ),
        "reader_uses_standard_library_only": "import appworld" not in inventory_source and "requests" not in inventory_source and "subprocess" not in inventory_source,
        "runner_does_not_import_or_install_appworld": "import appworld" not in runner_source and "pip install" not in runner_source and "appworld install" not in runner_source and "appworld download" not in runner_source,
        "runner_requires_revision_cleanliness_and_external_absolute_wheel": all(text in runner_source for text in ("project_revision_matches", "tracked_worktree_clean", "wheel_path_is_absolute", "wheel_is_outside_tracked_project")),
        "zip_limits_are_positive_and_bounded": all(isinstance(value, int) and not isinstance(value, bool) and value > 0 for value in config["zip_safety_limits"].values()),
        "output_is_atomic_and_does_not_copy_member_bytes": config["output_contract"]["atomic_json_write"] and not config["output_contract"]["raw_wheel_copied_into_project"] and not config["output_contract"]["member_bytes_persisted"],
        "five_wheel_reader_tests_pass": tests.returncode == 0 and "Ran 5 tests" in tests.stderr,
        "closed_result_schema": schema["additionalProperties"] is False and set(schema["required"]) == set(schema["properties"]),
        "closed_preparation_schema": preparation_schema["additionalProperties"] is False and set(preparation_schema["required"]) == set(preparation_schema["properties"]),
        "all_model_task_and_claim_boundaries_closed": all(value is False for value in boundary.values()),
    }
    result = {
        "schema_version": 1,
        "run_kind": "proper_v2_3_appworld_offline_wheel_inventory_preparation",
        "checks": checks,
        "passed": all(checks.values()),
        "config_sha256": sha256(CONFIG),
        "runner_sha256": sha256(RUNNER),
        "inventory_implementation_sha256": sha256(INVENTORY),
        "official_wheel_sha256": release["sha256"],
        "tests_run": 5,
        "wheel_downloaded": False,
        "wheel_read": False,
        "wheel_extracted": False,
        "protected_bundle_opened": False,
        "task_or_api_data_read": False,
        "model_loaded": False,
        "gpu_used": False,
        "remote_wheel_inventory_authorized": all(checks.values()),
        "source_install_authorized": False,
        "next_gate": config["next_gate_on_validation_pass"] if all(checks.values()) else "stop_wheel_inventory_preparation",
    }
    return result


def main() -> int:
    result = validate()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
