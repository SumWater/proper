"""Freeze and independently validate the returned native tau3 CPU smoke."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
FREEZE = ROOT / "configs/proper_v2_3/tau3_branch_replay_native_result_v2_3.json"
SMOKE_CONFIG = ROOT / "configs/proper_v2_3/tau3_branch_replay_native_smoke_v2_3.json"
SCHEMA = ROOT / "schemas/proper_v2_3/tau3_branch_replay_native_smoke.schema.json"
OUTPUT = ROOT / "outputs/proper_v2_3/tau3_branch_replay_native_smoke/local_freeze_validation.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate() -> dict[str, Any]:
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    expected = freeze["result"]
    result_path = ROOT / expected["path"]
    result = json.loads(result_path.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    schema_valid = schema.get("additionalProperties") is False
    try:
        import jsonschema
    except ImportError:
        schema_mode = "closed_shape_without_optional_jsonschema_dependency"
        schema_valid = schema_valid and set(schema["required"]).issubset(result)
    else:
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(result)
        schema_mode = "draft_2020_12_jsonschema"
    checks = {
        "result_sha256_matches": _sha256(result_path) == expected["sha256"],
        "remote_project_revision_matches": result["project_revision"] == expected["remote_project_revision"],
        "tau3_revision_matches": result["tau3_revision"] == expected["tau3_revision"],
        "smoke_config_hash_matches_result": result["config_sha256"] == expected["smoke_config_sha256"],
        "smoke_config_hash_matches_local": _sha256(SMOKE_CONFIG) == expected["smoke_config_sha256"],
        "all_native_checks_pass": len(result["checks"]) == expected["expected_check_count"] and all(result["checks"].values()),
        "checkpoint_round_trip_exact": result["checkpoint_sha256"] == expected["checkpoint_sha256"] == result["restored_checkpoint_sha256"],
        "native_execution_exactly_once": result["native_execution_count"] == expected["expected_native_execution_count"],
        "no_task_model_or_gpu": not any((result["task_loaded"], result["model_loaded"], result["model_outputs_read"], result["gpu_used"])),
        "model_and_confirmatory_gates_closed": not any((result["model_runner_authorized"], result["model_run_authorized"], result["confirmatory_run_authorized"])),
        "schema_valid": schema_valid,
    }
    passed = all(checks.values()) and result["passed"]
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_3_tau3_branch_replay_native_result_freeze_validation",
        "checks": checks,
        "passed": passed,
        "result_path": expected["path"],
        "result_sha256": _sha256(result_path),
        "remote_project_revision": result["project_revision"],
        "tau3_revision": result["tau3_revision"],
        "checkpoint_sha256": result["checkpoint_sha256"],
        "schema_validation_mode": schema_mode,
        "native_execution_count": result["native_execution_count"],
        "task_loaded": False,
        "model_loaded": False,
        "model_outputs_read": False,
        "gpu_used": False,
        "public_branch_capture_protocol_design_authorized": passed,
        "real_branch_capture_execution_authorized": False,
        "model_runner_authorized": False,
        "model_run_authorized": False,
        "confirmatory_run_authorized": False,
        "next_gate": "freeze_real_public_branch_capture_protocol",
    }


def main() -> int:
    result = validate()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
