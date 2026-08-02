"""CPU-only validation of the real public branch capture protocol design."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/proper_v2_3/real_public_branch_capture_protocol_v2_3.json"
SCHEMA = ROOT / "schemas/proper_v2_3/real_public_branch_capture_manifest.schema.json"
OUTPUT = ROOT / "outputs/proper_v2_3/real_public_branch_capture_protocol/validation.json"


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate() -> dict[str, Any]:
    config = _load(CONFIG)
    candidate_input = config["inputs"]["candidate_config"]
    candidates = _load(ROOT / candidate_input["path"])["candidates"]
    registry = {item["tool_name"]: item for item in config["public_action_registry"]}
    phases = Counter(item["phase"] for item in candidates)
    effects = Counter(item["effect_class"] for item in candidates)
    guarded_tools = {item["guarded_action_name"] for item in candidates}
    registry_matches = all(
        candidate["guarded_action_name"] in registry
        and registry[candidate["guarded_action_name"]]["effect_class"] == candidate["effect_class"]
        for candidate in candidates
    )
    verifiers_public_read_only = all(
        item["verifier_tool"] is None
        or item["verifier_tool"] in registry
        and registry[item["verifier_tool"]]["effect_class"] == "read_only"
        for item in registry.values()
    )
    input_hashes = {
        name: _sha256(ROOT / item["path"])
        for name, item in config["inputs"].items()
        if isinstance(item, dict) and "path" in item
    }
    expected_hashes = {
        name: item["sha256"]
        for name, item in config["inputs"].items()
        if isinstance(item, dict) and "path" in item
    }
    schema = _load(SCHEMA)
    method_fields = set(config["separation"]["method_fields"])
    evaluator_fields = set(config["separation"]["evaluator_only_fields"])
    checks = {
        "all_frozen_input_hashes_match": input_hashes == expected_hashes,
        "candidate_partition_is_12_development_pairs": len(candidates) == 12 and not config["partition"]["heldout"] and not config["partition"]["confirmatory"],
        "phase_balance_matches": phases == {"pre_action": 4, "post_failure": 8},
        "effect_balance_matches": effects == {"read_only": 4, "idempotent_state_setting": 4, "non_idempotent_side_effect": 4},
        "registry_covers_all_guarded_tools": guarded_tools.issubset(registry) and registry_matches,
        "all_declared_verifiers_are_public_read_only": verifiers_public_read_only,
        "state_settings_are_not_executed_during_injection": config["injection"]["idempotent_state_setting"]["native_execution"] == "suppressed",
        "non_idempotent_actions_execute_exactly_once": config["injection"]["non_idempotent_side_effect"]["native_execution"] == "exactly_once",
        "method_and_evaluator_fields_are_disjoint": method_fields.isdisjoint(evaluator_fields),
        "gold_and_evaluator_outcomes_not_used_for_routing": not config["separation"]["future_gold_actions_used_for_capture_routing"] and not config["separation"]["evaluator_outcome_used_for_capture_routing"],
        "one_attempt_without_replacement": config["acquisition"]["attempts_per_pair"] == 1 and not config["acquisition"]["resampling_allowed"] and not config["partition"]["replacement_candidates_allowed_after_capture_output"],
        "failure_results_are_preserved_and_stage_stops": all("preserve" in value or value == "forbidden" for value in config["failure_dispositions"].values()),
        "future_manifest_schema_is_closed": schema["additionalProperties"] is False,
        "capture_execution_and_model_gates_closed": not any((config["gates"]["authorize_real_branch_capture_execution"], config["gates"]["authorize_model_protocol"], config["gates"]["authorize_model_runner"], config["gates"]["authorize_gpu"], config["gates"]["authorize_confirmatory_claim"])),
    }
    passed = all(checks.values())
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_3_real_public_branch_capture_protocol_validation",
        "config_sha256": _sha256(CONFIG),
        "checks": checks,
        "passed": passed,
        "candidate_count": len(candidates),
        "phase_counts": dict(sorted(phases.items())),
        "effect_counts": dict(sorted(effects.items())),
        "guarded_tool_count": len(guarded_tools),
        "registry_tool_count": len(registry),
        "task_executed": False,
        "model_loaded": False,
        "model_outputs_read": False,
        "gpu_used": False,
        "capture_runtime_freeze_authorized": passed,
        "real_branch_capture_execution_authorized": False,
        "model_protocol_authorized": False,
        "model_runner_authorized": False,
        "confirmatory_run_authorized": False,
        "next_gate": "freeze_real_branch_capture_runtime",
    }


def main() -> int:
    result = validate()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
