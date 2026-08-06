"""Validate the no-decryption controlled-install protocol design."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/proper_v2_3/appworld_controlled_install_static_inventory_protocol_v2_3.json"
SCHEMA = ROOT / "schemas/proper_v2_3/appworld_controlled_install_static_inventory_protocol_validation.schema.json"
OUTPUT = ROOT / "outputs/proper_v2_3/appworld_controlled_install_protocol/validation.json"
if str(ROOT / "experiments/proper_v2_3") not in sys.path:
    sys.path.insert(0, str(ROOT / "experiments/proper_v2_3"))

from scripted_appworld_controlled_install_protocol_v2_3 import run_traces


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate() -> dict[str, Any]:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    official = config["official_public_install_observation"]
    bundle = config["protected_apps_bundle"]
    crypto = config["cryptographic_contract_from_public_source"]
    safety = config["decrypted_zip_safety"]
    privacy = config["privacy_and_license_output"]
    future = config["future_static_api_inventory_contract"]
    boundary = config["boundary"]
    traces = run_traces()
    tests = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_proper_v2_3_appworld_controlled_install_protocol"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    checks = {
        "wheel_inventory_freeze_hashes_match": all(sha256(ROOT / item["path"]) == item["sha256"] for item in config["frozen_inputs"]),
        "official_overbroad_and_destructive_commands_forbidden": official["package_install_also_decrypts_tests_bundle"] and official["official_unpack_uses_zip_extractall"] and official["data_download_removes_existing_data_directory"] and not official["official_install_command_allowed"] and not official["official_data_download_command_allowed"],
        "exact_apps_bundle_identity_frozen": bundle["encrypted_bytes"] == 177209 and bundle["encrypted_sha256"] == "ba58bc5679c3573aa8f60ad6f5cda4377128a0ec569de5eef9543a77561796bb",
        "tests_and_data_bundles_forbidden": bundle["tests_bundle_must_not_be_decrypted"] and bundle["data_bundle_must_not_be_downloaded"],
        "public_crypto_contract_is_exact_and_in_memory": crypto == {"kdf":"PBKDF2HMAC-SHA256","iterations":100000,"derived_key_bytes":32,"cipher":"AES-256-CFB","iv_prefix_bytes":16,"decrypt_in_memory_only":True},
        "all_zip_members_validated_before_extraction": all(safety[key] for key in ("reject_absolute_parent_or_backslash_paths", "reject_duplicate_members", "reject_symbolic_links")) and not safety["extract_during_bundle_inventory"],
        "protected_plaintext_never_persisted": not any(privacy[key] for key in ("persist_plaintext_member_paths", "persist_decrypted_member_bytes", "persist_source_snippets", "persist_api_or_app_names")) and privacy["raw_protected_inventory_stays_outside_git"],
        "aggregate_and_hashed_evidence_preserved": all(privacy[key] for key in ("persist_path_sha256", "persist_content_sha256", "persist_extension_counts", "persist_total_counts_and_bytes", "persist_decrypted_zip_sha256")),
        "future_static_inventory_is_gold_free_and_single_action": not future["authorized_in_this_stage"] and future["tests_bundle_forbidden"] and future["data_and_tasks_forbidden"] and future["ground_truth_and_evaluator_forbidden"] and future["one_api_call_per_ledger_event_required"],
        "independent_zero_network_model_and_extraction_budgets": all(config["budgets"][key] == 0 for key in ("invalid_archive_budget", "extraction_budget", "network_request_budget", "model_request_budget")),
        "six_scripted_traces_stop_closed": len(traces) == 6 and sum(item["decision"].startswith("stop") for item in traces) == 5 and not any(item["decrypted"] or item["extracted"] or item["protected_plaintext_persisted"] for item in traces),
        "five_protocol_tests_pass": tests.returncode == 0 and "Ran 5 tests" in tests.stderr,
        "all_execution_and_claim_boundaries_closed": all(value is False for value in boundary.values()),
        "validation_schema_is_closed": schema["additionalProperties"] is False and set(schema["required"]) == set(schema["properties"]),
    }
    passed = all(checks.values())
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_3_appworld_controlled_install_static_inventory_protocol_validation",
        "checks": checks,
        "passed": passed,
        "config_sha256": sha256(CONFIG),
        "scripted_trace_count": len(traces),
        "apps_bundle_decrypted": False,
        "tests_bundle_decrypted": False,
        "data_downloaded": False,
        "source_extracted": False,
        "api_inventory_performed": False,
        "task_instruction_read": False,
        "ground_truth_or_evaluator_read": False,
        "model_loaded": False,
        "gpu_used": False,
        "bundle_inventory_implementation_authorized": passed,
        "protected_bundle_decryption_authorized": False,
        "source_install_authorized": False,
        "static_api_inventory_authorized": False,
        "model_run_authorized": False,
        "confirmatory_claim_authorized": False,
        "next_gate": config["next_gate"],
    }


def main() -> int:
    result = validate()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
