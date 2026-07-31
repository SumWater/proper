"""Validate the prospective v2.3 target-capacity audit design.

The stage intentionally does not acquire, play, or model-score a target.
Semantic-family fields are audit-only exclusion metadata and never enter the
method implementation under ``src/failure_memory/proper_v2/v2_3``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "configs" / "proper_v2_3" / "target_capacity_audit_v2_3.yaml"
FROZEN_INVENTORY = (
    ROOT
    / "outputs"
    / "proper_v2"
    / "toolsandbox_continuation_target_inventory_v2_2_1"
    / "audit.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"expected object in {path}")
    return payload


def validate_capacity_design(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = _load_json(config_path)
    inventory = _load_json(FROZEN_INVENTORY)
    frozen = config["current_toolsandbox_inventory"]
    if not isinstance(frozen, Mapping):
        raise ValueError("current_toolsandbox_inventory must be an object")
    inventory_hash = _sha256(FROZEN_INVENTORY)
    checks = {
        "input_only_mode": config.get("mode") == "input_only_no_model_no_play",
        "frozen_inventory_hash": inventory_hash == frozen.get("source_sha256"),
        "frozen_inventory_count": (
            inventory["summary"]["all_named_scenario_count"]
            == frozen.get("scenario_name_count")
            == 1032
        ),
        "frozen_inventory_zero_candidates": (
            inventory["summary"]["candidate_count"]
            == frozen.get("eligible_candidate_count")
            == 0
        ),
        "exhausted_pool_not_relabelled": (
            frozen.get("inventory_exhausted") is True
            and frozen.get("rescreen_as_heldout_allowed") is False
        ),
        "prospective_three_way_partition": config.get("prospective_partitions")
        == ["development", "heldout", "preservation"],
        "no_candidate_source_claimed": config.get("candidate_sources") == [],
        "no_gpu_or_model_authority": all(
            config["boundary"].get(key) is False
            for key in (
                "model_loaded",
                "model_outputs_read",
                "target_scenarios_played",
                "gpu_run_authorized",
                "confirmatory_claim_authorized",
            )
        ),
    }
    passed = all(checks.values())
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_3_target_capacity_design_validation",
        "checks": checks,
        "passed": passed,
        "candidate_source_count": len(config.get("candidate_sources", [])),
        "new_target_capacity_available": False,
        "development_model_run_authorized": False,
        "confirmatory_run_authorized": False,
        "disposition": "stop_no_target_capacity",
        "interpretation": (
            "The design is ready for future source acquisition, but no genuinely "
            "unexposed target source is currently registered."
        ),
    }


def main() -> int:
    result = validate_capacity_design()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
