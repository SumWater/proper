"""Validate the PlanBench-XL no-model capacity-audit design.

The script deliberately stops before inventory while the external source has
not been acquired and frozen.  It performs no network access or task play.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = (
    ROOT / "configs/proper_v2_3/planbench_xl_capacity_audit_design_v2_3.json"
)


def _load(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("capacity-audit configuration must be an object")
    return payload


def validate_planbench_xl_audit_design(
    config_path: Path = DEFAULT_CONFIG,
) -> dict[str, Any]:
    config = _load(config_path)
    source = config["source"]
    boundary = config["boundary"]
    sequence = config["qualification_sequence"]
    audit_fields = set(config["audit_only_fields_never_passed_to_method"])
    checks = {
        "design_is_no_model_no_play": config["mode"]
        == "static_metadata_and_structure_only_no_model_no_play",
        "source_is_not_falsely_frozen": (
            source["local_source_acquired"] is False
            and source["local_revision"] is None
            and source["local_input_sha256"] is None
        ),
        "source_locations_are_explicit": all(
            str(source[key]).startswith("https://")
            for key in ("paper_url", "project_url", "repository_url", "dataset_url")
        ),
        "freeze_precedes_inventory": sequence[:2]
        == [
            "freeze_source_revision_and_input_hashes",
            "structural_inventory_without_model_or_task_play",
        ],
        "partition_precedes_model_gate": sequence.index(
            "freeze_development_heldout_preservation_partitions"
        )
        < sequence.index("run_model_free_base_capability_gate_before_failure_intervention"),
        "gold_fields_are_audit_only": {
            "correct_answer",
            "golden_tool_path",
            "blocking_annotation",
            "benchmark_completion_label",
            "semantic_family",
        }.issubset(audit_fields),
        "observable_recovery_requirements_present": all(
            config["candidate_requirements"][key]
            for key in (
                "public_tool_schema_available",
                "public_action_effect_evidence_available",
                "failure_is_observable_to_method",
                "recovery_path_remains_available",
                "observable_success_verification_available",
                "method_does_not_require_gold_path",
            )
        ),
        "no_external_or_gpu_action": all(
            boundary[key] is False
            for key in (
                "network_acquisition_performed",
                "model_loaded",
                "model_outputs_read",
                "target_scenarios_played",
                "gpu_run_authorized",
                "confirmatory_claim_authorized",
            )
        ),
        "base_capability_floor_stops_model_experiment": config["stop_rules"]
        ["qwen_base_capability_floor"]
        == "stop_model_experiment",
    }
    passed = all(checks.values())
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_3_planbench_xl_capacity_audit_design_validation",
        "checks": checks,
        "passed": passed,
        "source_acquired": False,
        "inventory_performed": False,
        "candidate_count": None,
        "model_loaded": False,
        "gpu_used": False,
        "model_run_authorized": False,
        "confirmatory_run_authorized": False,
        "disposition": "stop_before_inventory",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = validate_planbench_xl_audit_design(args.config)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
