from __future__ import annotations

import argparse
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
    / "toolsandbox_heldout_target_audit_v2_2.yaml"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("status") != "heldout_target_audit_before_v2_2_model_outputs":
        raise RuntimeError("held-out target audit config status is invalid")
    boundary = config["boundary"]
    if (
        boundary["model_outputs_read"]
        or boundary["target_scenarios_played"]
        or boundary["gpu_run_authorized"]
        or boundary["confirmatory_run_authorized"]
    ):
        raise RuntimeError("held-out target audit must remain CPU/input-only")
    return config


def load_inputs(
    config: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    loaded = {}
    for name, item in config["frozen_inputs"].items():
        path = ROOT / str(item["path"])
        observed = sha256_file(path)
        if observed != str(item["sha256"]):
            raise RuntimeError(
                f"held-out audit input hash mismatch: {path}; "
                f"expected={item['sha256']} observed={observed}"
            )
        loaded[name] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def audit(config_path: Path = CONFIG) -> dict[str, Any]:
    config = load_config(config_path)
    inputs = load_inputs(config)
    inventory = inputs["dynamic_inventory"]["records"]
    capacity = inputs["phase_aware_capacity"]
    prepared = inputs["v2_1_prepared_manifest"]
    exposed = {str(item["scenario_name"]) for item in prepared["records"]}
    source_families = set(capacity["source_target_split"]["source_families"])
    capacity_by_name = {
        str(item["scenario_name"]): item for item in capacity["records"]
    }

    records = []
    counts: Counter[str] = Counter()
    for item in inventory:
        name = str(item["name"])
        family = str(item["semantic_family"])
        capacity_record = capacity_by_name.get(name)
        if name in exposed:
            disposition = "excluded"
            reason = "v2_1_model_exposed_development_target"
        elif family in source_families:
            disposition = "excluded"
            reason = "memory_source_family_overlap"
        elif (
            capacity_record is not None
            and not bool(capacity_record["intervention_distinct"])
        ):
            disposition = "preservation_only"
            reason = "behaviorally_nonidentifiable_preservation_target"
        elif (
            capacity_record is not None
            and bool(capacity_record["intervention_distinct"])
        ):
            disposition = "eligible_effect_validation"
            reason = "unconsumed_behaviorally_distinct_target"
        else:
            disposition = "requires_capacity_screening"
            reason = "unconsumed_unscreened_target"
        counts[reason] += 1
        records.append(
            {
                "scenario_name": name,
                "semantic_family": family,
                "policy_categories": list(item["policy_categories"]),
                "disposition": disposition,
                "reason_code": reason,
                "v2_1_model_exposed": name in exposed,
                "memory_source_family_overlap": family in source_families,
                "capacity_screened": capacity_record is not None,
                "intervention_distinct": (
                    bool(capacity_record["intervention_distinct"])
                    if capacity_record is not None
                    else None
                ),
            }
        )

    summary = {
        "scenario_count": len(records),
        "v2_1_model_exposed_count": counts[
            "v2_1_model_exposed_development_target"
        ],
        "memory_source_family_overlap_count": counts[
            "memory_source_family_overlap"
        ],
        "preservation_only_count": counts[
            "behaviorally_nonidentifiable_preservation_target"
        ],
        "eligible_effect_validation_count": counts[
            "unconsumed_behaviorally_distinct_target"
        ],
        "requires_capacity_screening_count": counts[
            "unconsumed_unscreened_target"
        ],
    }
    expected = config["expected_current_inventory"]
    checks = {
        key: summary[key] == int(value) for key, value in expected.items()
    }
    eligible = summary["eligible_effect_validation_count"]
    unscreened = summary["requires_capacity_screening_count"]
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_2_toolsandbox_heldout_target_audit",
        "identities": {
            "config_sha256": sha256_file(config_path),
            "frozen_input_sha256": {
                name: str(item["sha256"])
                for name, item in config["frozen_inputs"].items()
            },
        },
        "summary": summary,
        "checks": checks,
        "audit_passed": all(checks.values()),
        "heldout_effect_validation_ready": eligible > 0,
        "next_action": (
            "freeze_eligible_unconsumed_targets"
            if eligible > 0
            else "screen_unconsumed_non_source_targets_without_model_outputs"
            if unscreened > 0
            else "acquire_new_non_source_scenario_families_then_repeat_capacity_audit"
        ),
        "records": records,
        "boundary": dict(config["boundary"]),
        "interpretation_limits": {
            "no_model_outputs_read": True,
            "preservation_targets_are_not_effect_identifiable": True,
            "source_family_targets_are_not_held_out": True,
            "zero_eligible_targets_does_not_authorize_confirmation": True,
        },
    }


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
        description="Audit unconsumed ToolSandbox targets for future holdout."
    )
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()
    config = load_config(args.config)
    result = audit(args.config)
    output = write_result(result, config)
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2, sort_keys=True))
    print(f"HELDOUT_EFFECT_VALIDATION_READY={result['heldout_effect_validation_ready']}")
    print(f"NEXT_ACTION={result['next_action']}")
    print(f"OUTPUT={output}")
    status = "PASS" if result["audit_passed"] else "STOP"
    print(f"RESULT={status}_PROPER_V2_2_HELDOUT_TARGET_AUDIT")
    return 0 if result["audit_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
