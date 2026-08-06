"""Validate aggregate-only apps-bundle inventory before real decryption."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/proper_v2_3/appworld_apps_bundle_inventory_implementation_v2_3.json"
RESULT_SCHEMA = ROOT / "schemas/proper_v2_3/appworld_apps_bundle_inventory.schema.json"
VALIDATION_SCHEMA = ROOT / "schemas/proper_v2_3/appworld_apps_bundle_inventory_implementation_validation.schema.json"
RUNNER = ROOT / "experiments/proper_v2_3/run_appworld_apps_bundle_inventory_remote_v2_3.py"
IMPLEMENTATION = ROOT / "src/failure_memory/proper_v2/v2_3/encrypted_bundle_inventory.py"
OUTPUT = ROOT / "outputs/proper_v2_3/appworld_apps_bundle_inventory_implementation/validation.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate() -> dict[str, Any]:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    result_schema = json.loads(RESULT_SCHEMA.read_text(encoding="utf-8"))
    validation_schema = json.loads(VALIDATION_SCHEMA.read_text(encoding="utf-8"))
    runner_source = RUNNER.read_text(encoding="utf-8")
    implementation_source = IMPLEMENTATION.read_text(encoding="utf-8")
    ast.parse(runner_source)
    ast.parse(implementation_source)
    tests = subprocess.run([sys.executable,"-m","unittest","tests.test_proper_v2_3_appworld_encrypted_bundle_inventory"],cwd=ROOT,capture_output=True,text=True,check=False)
    boundary = config["boundary"]
    gates = config["gates"]
    checks = {
        "all_frozen_implementation_inputs_match": all(sha256(ROOT / item["path"]) == item["sha256"] for item in config["frozen_inputs"]),
        "wheel_and_apps_bundle_identity_are_exact": config["wheel"]["sha256"] == "db77f8003982502383a50fa2974983894bd1c54f64e2fd3f7e1540d5edd037eb" and config["apps_bundle"]["encrypted_sha256"] == "ba58bc5679c3573aa8f60ad6f5cda4377128a0ec569de5eef9543a77561796bb",
        "public_crypto_material_is_bound_without_claiming_secret": config["public_crypto_material"]["source"].startswith("appworld/common/constants.py@wheel_sha256:") and config["public_crypto_material"]["iterations"] == 100000,
        "reader_decrypts_in_memory_and_never_extracts": "io.BytesIO(decrypted)" in implementation_source and "extractall" not in implementation_source and "write_bytes" not in implementation_source,
        "reader_persists_hashes_not_plaintext_paths": "path_sha256" in implementation_source and '"relative_path"' not in implementation_source and "protected_plaintext_persisted" in implementation_source,
        "runner_reads_only_exact_apps_member": 'archive.read(bundle["wheel_member_path"])' in runner_source and "tests.bundle" not in runner_source,
        "runner_has_no_network_appworld_import_install_or_model": all(text not in runner_source for text in ("import requests", "import appworld", "appworld install", "download_data", "transformers", "torch")),
        "runner_preflight_is_revision_clean_external_and_dependency_guarded": all(text in runner_source for text in ("project_revision_matches", "tracked_worktree_clean", "wheel_is_outside_tracked_project", "cryptography_version_allowed", "all_frozen_input_hashes_match")),
        "seven_synthetic_tests_pass_without_warning": tests.returncode == 0 and "Ran 7 tests" in tests.stderr and "Warning" not in tests.stderr,
        "result_and_validation_schemas_are_closed": result_schema["additionalProperties"] is False and set(result_schema["required"]) == set(result_schema["properties"]) and validation_schema["additionalProperties"] is False and set(validation_schema["required"]) == set(validation_schema["properties"]),
        "all_real_execution_boundaries_remain_closed": all(value is False for value in boundary.values()),
        "only_one_remote_bundle_inventory_gate_opens": gates["one_remote_apps_bundle_inventory_authorized_after_validation"] and not any(gates[key] for key in ("official_appworld_install_authorized", "source_install_authorized", "static_api_inventory_authorized", "model_run_authorized", "confirmatory_claim_authorized")),
    }
    passed = all(checks.values())
    return {
        "schema_version":1,
        "run_kind":"proper_v2_3_appworld_apps_bundle_inventory_implementation_validation",
        "checks":checks,
        "passed":passed,
        "implementation_config_sha256":sha256(CONFIG),
        "runner_sha256":sha256(RUNNER),
        "inventory_implementation_sha256":sha256(IMPLEMENTATION),
        "tests_run":7,
        "synthetic_bundle_decrypted":True,
        "real_apps_bundle_decrypted":False,
        "tests_bundle_read":False,
        "tests_bundle_decrypted":False,
        "data_downloaded":False,
        "source_extracted":False,
        "protected_plaintext_persisted":False,
        "task_or_api_data_read":False,
        "model_loaded":False,
        "gpu_used":False,
        "one_remote_bundle_inventory_authorized":passed,
        "source_install_authorized":False,
        "static_api_inventory_authorized":False,
        "model_run_authorized":False,
        "confirmatory_claim_authorized":False,
        "next_gate":"run_one_remote_aggregate_only_apps_bundle_inventory" if passed else "stop_bundle_inventory_implementation",
    }


def main() -> int:
    result=validate()
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_bytes((json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n").encode("utf-8"))
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
