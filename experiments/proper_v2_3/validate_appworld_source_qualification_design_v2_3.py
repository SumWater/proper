"""Validate the AppWorld prospective source design without acquiring it."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/proper_v2_3/appworld_source_qualification_design_v2_3.json"
OUTPUT = ROOT / "outputs/proper_v2_3/appworld_source_qualification_design/validation.json"


def load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError("AppWorld source design must be an object")
    return value


def validate(config_path: Path = CONFIG) -> dict[str, Any]:
    config = load(config_path)
    source = config["source"]
    exposure = config["exposure_boundary"]
    interface = config["execution_interface"]
    transport = config["participant_transport"]
    sequence = config["qualification_sequence"]
    boundary = config["boundary"]
    audit_only = set(config["audit_only_fields_never_passed_to_method"])
    checks = {
        "primary_source_metadata_only": config["mode"] == "primary_source_metadata_only_no_download_no_task_play_no_model",
        "source_not_falsely_frozen_or_acquired": (
            source["local_source_acquired"] is False
            and all(source[key] is None for key in ("frozen_upstream_revision", "frozen_code_version", "frozen_data_version", "frozen_source_manifest_sha256"))
        ),
        "paper_repository_and_project_are_explicit": all(str(source[key]).startswith("https://") for key in ("paper_url", "repository_url", "project_url")),
        "reported_scale_is_metadata_not_inventory": source["reported_app_count"] == 9 and source["reported_api_count"] == 457 and source["reported_task_count"] == 750,
        "protected_redistribution_boundary_is_explicit": source["public_code_license"] == "Apache-2.0" and source["protected_material_rule"] == "public_redistribution_only_in_encrypted_format",
        "version_freeze_precedes_inventory": sequence.index("freeze_exact_upstream_revision_code_version_data_version_and_manifest") < sequence.index("inventory_ids_splits_and_public_api_schemas_without_ground_truth_or_task_play"),
        "partition_freeze_precedes_any_qwen_output": sequence.index("freeze_development_heldout_and_preservation_ids_before_any_qwen_output") < sequence.index("run_disjoint_base_capability_calibration_without_failure_memory"),
        "project_unconsumed_is_not_model_unexposed_or_heldout": (
            exposure["may_be_called_project_unconsumed_after_hash_audit"]
            and not exposure["may_be_called_foundation_model_unexposed"]
            and not exposure["may_be_called_heldout_now"]
            and not exposure["may_be_called_confirmatory_now"]
        ),
        "single_intercepted_action_is_required": (
            interface["agent_action_unit"] == "one_named_appworld_api_call"
            and not interface["arbitrary_multi_api_code_block_allowed"]
            and interface["every_api_proposal_recorded_before_execution"]
            and interface["complete_trajectory_action_execution_ledger_required"]
        ),
        "state_evidence_and_unknown_stop_are_required": interface["database_checkpoint_before_state_changing_action"] and interface["database_checkpoint_after_state_changing_action"] and interface["unknown_effect_stops_closed"],
        "new_transport_does_not_reopen_tau3": (
            transport["user_message_is_plain_public_text"]
            and not transport["user_message_requires_json_wrapper"]
            and transport["agent_action_requires_closed_schema"]
            and transport["invalid_outputs_count_toward_cost"]
            and not transport["same_tau3_cohort_rerun_or_replacement"]
        ),
        "gold_and_evaluator_fields_are_audit_only": {"ground_truth", "required_apps", "required_apis", "answer", "evaluation_code", "api_calls", "compiled_solution_module", "benchmark_completion_label", "semantic_family"}.issubset(audit_only),
        "effect_coverage_gate_is_complete": config["capacity_gates"]["minimum_idempotent_state_setting_pairs"] >= 3 and config["capacity_gates"]["minimum_non_idempotent_side_effect_pairs"] >= 3 and config["capacity_gates"]["maximum_unknown_effect_pairs"] == 0,
        "all_execution_and_claim_boundaries_closed": all(value is False for value in boundary.values()),
    }
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_3_appworld_source_qualification_design_validation",
        "checks": checks,
        "passed": all(checks.values()),
        "source_acquired": False,
        "inventory_performed": False,
        "task_instruction_read": False,
        "ground_truth_read": False,
        "candidate_count": None,
        "model_loaded": False,
        "gpu_used": False,
        "model_run_authorized": False,
        "confirmatory_run_authorized": False,
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
