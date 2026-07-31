from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
CONFIG = (
    ROOT
    / "configs"
    / "proper_v2"
    / "toolsandbox_continuation_conditions_preparation_v2_2_1.yaml"
)


def canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if (
        config.get("status")
        != "continuation_condition_preparation_development_only"
    ):
        raise RuntimeError("continuation preparation config status is invalid")
    boundary = config["boundary"]
    if (
        not boundary["development_only"]
        or boundary["model_loaded"]
        or boundary["model_outputs_read_by_preparation"]
        or boundary["target_scenarios_played"]
        or boundary["gpu_run_authorized"]
        or boundary["confirmatory_claim_authorized"]
    ):
        raise RuntimeError("continuation preparation boundary is invalid")
    item = config["frozen_inputs"]["v2_1_prepared_manifest"]
    target = ROOT / str(item["path"])
    observed = sha256_file(target)
    if observed != str(item["sha256"]):
        raise RuntimeError(
            "v2.1 prepared manifest hash mismatch: "
            f"expected={item['sha256']} observed={observed}"
        )
    return config


def prepare_manifest(config_path: Path = CONFIG) -> dict[str, Any]:
    config = load_config(config_path)
    source_item = config["frozen_inputs"]["v2_1_prepared_manifest"]
    source = json.loads(
        (ROOT / str(source_item["path"])).read_text(encoding="utf-8")
    )
    variants = list(config["condition_variants"])
    variant_names = [str(item["name"]) for item in variants]
    if len(variant_names) != len(set(variant_names)):
        raise RuntimeError("condition variant names must be unique")

    records = []
    for source_record in source["records"]:
        record = copy.deepcopy(source_record)
        conditions = {}
        for variant in variants:
            name = str(variant["name"])
            source_name = str(variant["source_condition"])
            if source_name not in source_record["conditions"]:
                raise RuntimeError(
                    f"missing source condition {source_name} "
                    f"for {source_record['pair_id']}"
                )
            condition = copy.deepcopy(source_record["conditions"][source_name])
            condition["source_condition"] = source_name
            condition["intervention"] = {
                "report_name": str(variant["report_name"]),
                "selector": str(variant["selector"]),
                "memory_exposure": str(variant["memory_exposure"]),
                "continuation_controller": bool(
                    variant["continuation_controller"]
                ),
            }
            conditions[name] = condition
        record["conditions"] = conditions
        records.append(record)

    phase_counts = dict(
        sorted(Counter(str(item["decision_phase"]) for item in records).items())
    )
    condition_count = sum(len(item["conditions"]) for item in records)
    expected = config["expected"]
    checks = {
        "pair_count": len(records) == int(expected["pair_count"]),
        "condition_count": condition_count == int(expected["condition_count"]),
        "condition_count_per_pair": all(
            len(item["conditions"])
            == int(expected["condition_count_per_pair"])
            for item in records
        ),
        "phase_counts": (
            phase_counts.get("pre_action", 0)
            == int(expected["pre_action_pair_count"])
            and phase_counts.get("post_failure", 0)
            == int(expected["post_failure_pair_count"])
        ),
        "source_initial_requests_unchanged": all(
            condition["initial_request_sha256"]
            == sha256_text(canonical(condition["initial_request"]))
            for record in records
            for condition in record["conditions"].values()
        ),
        "proper_variants_share_selection": all(
            record["conditions"]["proper_v2_1_memory"]["experience_id"]
            == record["conditions"]["proper_lifecycle_prompt_only"][
                "experience_id"
            ]
            == record["conditions"]["proper_lifecycle_replan_controller"][
                "experience_id"
            ]
            for record in records
        ),
    }
    cohort = copy.deepcopy(source["cohort"])
    cohort.update(
        {
            "condition_order": variant_names,
            "condition_count": condition_count,
            "condition_count_per_pair": len(variants),
            "source_pair_count": len(records),
            "comparison_design": "same_start_four_condition_development",
        }
    )
    agent_budget = copy.deepcopy(source["agent_budget"])
    agent_budget["memory_injected_on_each_decision"] = (
        "condition_specific"
    )
    result = {
        "schema_version": 1,
        "run_kind": "proper_v2_2_1_continuation_condition_manifest",
        "status": "prepared_development_only",
        "identities": {
            "config_sha256": sha256_file(config_path),
            "source_manifest_sha256": source_item["sha256"],
        },
        "agent_budget": agent_budget,
        "cohort": cohort,
        "model_protocol": copy.deepcopy(source["model_protocol"]),
        "evaluation": copy.deepcopy(source["evaluation"]),
        "preparation_checks": checks,
        "ready_for_development_runner": all(checks.values()),
        "ready_for_runner_implementation": all(checks.values()),
        "records": records,
        "boundary": dict(config["boundary"]),
        "interpretation_limits": {
            "v2_1_pairs_are_model_exposed_development_data": True,
            "condition_cloning_does_not_create_heldout_data": True,
            "no_model_behavior_tested": True,
            "no_target_scenario_played": True,
        },
    }
    result["identities"]["prepared_payload_sha256"] = sha256_text(
        canonical(result)
    )
    return result


def write_result(
    result: Mapping[str, Any],
    config: Mapping[str, Any],
) -> Path:
    output = ROOT / str(config["output"]["path"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare four same-start continuation development conditions."
    )
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()
    config = load_config(args.config)
    result = prepare_manifest(args.config)
    output = write_result(result, config)
    print(
        json.dumps(
            {
                "ready": result["ready_for_development_runner"],
                "pair_count": len(result["records"]),
                "condition_count": result["cohort"]["condition_count"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    print(f"OUTPUT={output}")
    status = "PASS" if result["ready_for_development_runner"] else "STOP"
    print(f"RESULT={status}_CONTINUATION_CONDITION_PREPARATION_V2_2_1")
    return 0 if result["ready_for_development_runner"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
