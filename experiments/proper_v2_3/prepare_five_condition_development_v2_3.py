"""Prepare the frozen 12x5 PROPER v2.3 development manifest without a model."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "configs" / "proper_v2_3" / "five_condition_development_v2_3.yaml"


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verify_frozen_inputs(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    declared = [
        {"role": "protocol", **config["protocol"]},
        {"role": "prompts", **config["prompts"]},
        *config["frozen_inputs"],
    ]
    checks: list[dict[str, Any]] = []
    for item in declared:
        path = ROOT / item["path"]
        actual = sha256(path)
        checks.append({
            "role": item["role"], "path": item["path"],
            "expected_sha256": item["sha256"], "actual_sha256": actual,
            "passed": actual == item["sha256"],
        })
    return checks


def fifth_condition(record: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, Any]:
    source = copy.deepcopy(record["conditions"]["proper_lifecycle_replan_controller"])
    source["runtime_request_namespace"] = (
        f"{record['pair_id']}:proper_v2_3_full_ledger_controller"
    )
    source["intervention"] = {
        "report_name": "proper_v2_3_full_action_ledger_controller",
        "selector": "proper_v2_1",
        "memory_exposure": "consume_and_remove",
        "continuation_controller": True,
        "execution_controller": "proper_v2_3_complete_trajectory",
        "complete_trajectory_ledger": True,
        "observable_input_only": True,
        "effect_contract_source": "public_tool_contract_only",
        "controller_budget": copy.deepcopy(config["controller_budget"]),
        "forbidden_method_inputs": copy.deepcopy(config["exclusions"]["forbidden_method_inputs"]),
    }
    return source


def prepare(
    config_path: Path = DEFAULT_CONFIG,
    run_id: str = "static-preparation-validation",
) -> dict[str, Any]:
    config = load_object(config_path)
    if config["status"] != "frozen_five_condition_preparation_before_any_v2_3_model_output":
        raise RuntimeError("five-condition preparation config is not frozen")
    input_checks = verify_frozen_inputs(config)
    source_path = ROOT / config["frozen_inputs"][0]["path"]
    source = load_object(source_path)
    source_records = source["records"]
    records: list[dict[str, Any]] = []
    source_condition_snapshots: list[str] = []
    proper_initial_identity: list[bool] = []
    fifth_memory_identity: list[bool] = []
    fifth_controller_identity: list[bool] = []
    forbidden_absent: list[bool] = []
    forbidden = set(config["exclusions"]["forbidden_method_inputs"])
    for source_record in source_records:
        record = copy.deepcopy(source_record)
        source_condition_snapshots.append(canonical_sha256(record["conditions"]))
        fifth = fifth_condition(record, config)
        record["conditions"]["proper_v2_3_full_ledger_controller"] = fifth
        proper_names = [item["name"] for item in config["conditions"] if item["selector"] == "proper_v2_1"]
        initial_hashes = {
            canonical_sha256(record["conditions"][name]["initial_request"])
            for name in proper_names
        }
        proper_initial_identity.append(len(initial_hashes) == 1)
        fourth = record["conditions"]["proper_lifecycle_replan_controller"]
        fifth_memory_identity.append(fifth["memory"] == fourth["memory"])
        fifth_controller_identity.append(
            fifth["intervention"]["execution_controller"] == "proper_v2_3_complete_trajectory"
            and fifth["intervention"]["complete_trajectory_ledger"] is True
        )
        forbidden_absent.append(not (forbidden & set(fifth)))
        records.append(record)
    phase_counts = {
        phase: sum(item["decision_phase"] == phase for item in records)
        for phase in ("pre_action", "post_failure")
    }
    source_unchanged = all(
        canonical_sha256({key: value for key, value in record["conditions"].items()
                          if key != "proper_v2_3_full_ledger_controller"}) == snapshot
        for record, snapshot in zip(records, source_condition_snapshots)
    )
    checks = {
        "all_input_hashes_match": all(item["passed"] for item in input_checks),
        "source_pair_count_matches": len(records) == config["cohort"]["pair_count"],
        "phase_counts_match": (
            phase_counts["pre_action"] == config["cohort"]["pre_action_pair_count"]
            and phase_counts["post_failure"] == config["cohort"]["post_failure_pair_count"]
        ),
        "five_conditions_per_pair": all(len(item["conditions"]) == 5 for item in records),
        "source_four_conditions_unchanged": source_unchanged,
        "proper_initial_requests_byte_identical": all(proper_initial_identity),
        "fifth_memory_matches_condition_four": all(fifth_memory_identity),
        "fifth_controller_is_full_trajectory": all(fifth_controller_identity),
        "forbidden_method_inputs_absent_from_fifth_condition": all(forbidden_absent),
        "no_model_output_content_read": True,
        "ready_for_runner_implementation": False,
    }
    ready = all(value for key, value in checks.items() if key != "ready_for_runner_implementation")
    checks["ready_for_runner_implementation"] = ready
    result = {
        "schema_version": 2,
        "run_kind": "proper_v2_3_five_condition_prepared_manifest_v2",
        "run_id": run_id,
        "status": "passed" if ready else "failed",
        "config_sha256": sha256(config_path),
        "protocol_sha256": config["protocol"]["sha256"],
        "prompts_sha256": config["prompts"]["sha256"],
        "input_hash_checks": input_checks,
        "conditions": copy.deepcopy(config["conditions"]),
        "cohort": {
            key: config["cohort"][key] for key in (
                "pair_count", "pre_action_pair_count", "post_failure_pair_count",
                "condition_count_per_pair", "total_condition_count",
            )
        },
        "preparation_checks": checks,
        "records": records,
        "boundary": {
            "development_only": True, "existing_model_exposed_pairs": True,
            "model_runner_implemented": False, "model_loaded": False,
            "gpu_used": False, "target_scenarios_played": False,
            "development_model_run_authorized": False,
            "confirmatory_claim_authorized": False, "heldout_claim_authorized": False,
            "new_heldout_target_capacity": 0,
        },
        "next_gate": config["next_gate_on_pass"] if ready else config["next_gate_on_failure"],
    }
    return result


def write_result(result: Mapping[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    config_path = args.config.resolve()
    config = load_object(config_path)
    output = (args.output or (
        ROOT / config["output"]["root"] / "manual-preparation" /
        config["output"]["prepared_manifest_name"]
    )).resolve()
    if output.exists() and config["output"]["never_overwrite"]:
        raise FileExistsError(f"refusing to overwrite prepared manifest: {output}")
    result = prepare(config_path, run_id="manual-preparation")
    write_result(result, output)
    print(json.dumps({"status": result["status"], "pairs": len(result["records"]),
                      "conditions": sum(len(item["conditions"]) for item in result["records"]),
                      "model_run_authorized": False, "output": str(output)}, sort_keys=True))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
