"""One-shot CPU validation for the tau3 model-protocol feasibility gate."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from tau3_model_protocol_feasibility_v2_3 import DEFAULT_CONFIG, DEFAULT_OUTPUT, run_audit

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas/proper_v2_3/tau3_model_protocol_feasibility.schema.json"
VALIDATION_OUTPUT = ROOT / "outputs/proper_v2_3/tau3_model_protocol_feasibility/validation.json"
STAGE_INPUTS = (
    "configs/proper_v2_3/tau3_model_protocol_feasibility_v2_3.json",
    "docs/proper_v2_3/tau3_model_protocol_feasibility_result.md",
    "experiments/proper_v2_3/tau3_model_protocol_feasibility_v2_3.py",
    "experiments/proper_v2_3/validate_tau3_model_protocol_feasibility_v2_3.py",
    "schemas/proper_v2_3/tau3_model_protocol_feasibility.schema.json",
    "tests/test_proper_v2_3_tau3_model_protocol_feasibility.py",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate() -> dict[str, Any]:
    audit = run_audit(DEFAULT_CONFIG)
    DEFAULT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_OUTPUT.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    schema_valid = schema.get("additionalProperties") is False
    try:
        import jsonschema
    except ImportError:
        schema_mode = "closed_shape_without_optional_jsonschema_dependency"
        schema_valid = schema_valid and set(schema["required"]).issubset(audit)
    else:
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(audit)
        schema_mode = "draft_2020_12_jsonschema"
    tests = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_proper_v2_3_tau3_model_protocol_feasibility"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    hashes = {relative: _sha256(ROOT / relative) for relative in STAGE_INPUTS}
    checks = {
        "audit_passed": audit["audit_passed"],
        "source_actions_map_12_of_12": audit["summary"]["source_action_mapping_count"] == 12,
        "only_four_public_task_starts_ready": audit["summary"]["model_ready_count"] == 4,
        "zero_post_failure_branches_ready": audit["summary"]["model_ready_phase_counts"]["post_failure"] == 0,
        "model_protocol_not_authorized": not audit["model_protocol_freeze_authorized"],
        "runner_implementation_not_authorized": not audit["model_runner_implementation_authorized"],
        "closed_schema_valid": schema_valid,
        "scoped_tests_pass": tests.returncode == 0,
        "all_stage_inputs_hashed": len(hashes) == len(STAGE_INPUTS),
    }
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_3_tau3_model_protocol_feasibility_stage_validation",
        "checks": checks,
        "passed": all(checks.values()),
        "audit_path": DEFAULT_OUTPUT.relative_to(ROOT).as_posix(),
        "audit_sha256": _sha256(DEFAULT_OUTPUT),
        "schema_validation_mode": schema_mode,
        "scoped_tests_run": 3,
        "stage_input_sha256": hashes,
        "task_executed": False,
        "model_loaded": False,
        "model_outputs_read": False,
        "gpu_used": False,
        "development_model_run_authorized": False,
        "confirmatory_run_authorized": False,
        "next_gate": "design_public_branch_capture_without_model_exposure",
    }


def main() -> int:
    result = validate()
    VALIDATION_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    VALIDATION_OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
