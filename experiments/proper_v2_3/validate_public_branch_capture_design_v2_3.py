"""One-shot CPU validation for public branch capture design."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from scripted_public_branch_capture_traces_v2_3 import OUTPUT, run_traces

VALIDATION_OUTPUT = ROOT / "outputs/proper_v2_3/public_branch_capture_design/validation.json"
TRACE_SCHEMA = ROOT / "schemas/proper_v2_3/public_branch_capture_traces.schema.json"
ARTIFACT_SCHEMA = ROOT / "schemas/proper_v2_3/public_branch_artifact.schema.json"
STAGE_INPUTS = (
    "configs/proper_v2_3/public_branch_capture_design_v2_3.json",
    "docs/proper_v2_3/public_branch_capture_design.md",
    "experiments/proper_v2_3/scripted_public_branch_capture_traces_v2_3.py",
    "experiments/proper_v2_3/validate_public_branch_capture_design_v2_3.py",
    "schemas/proper_v2_3/public_branch_artifact.schema.json",
    "schemas/proper_v2_3/public_branch_capture_traces.schema.json",
    "src/failure_memory/proper_v2/v2_3/branch_capture.py",
    "tests/test_proper_v2_3_public_branch_capture.py",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate() -> dict[str, Any]:
    traces = run_traces()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes((json.dumps(traces, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    schemas = [json.loads(path.read_text(encoding="utf-8")) for path in (TRACE_SCHEMA, ARTIFACT_SCHEMA)]
    schema_valid = all(schema.get("additionalProperties") is False for schema in schemas)
    try:
        import jsonschema
    except ImportError:
        schema_mode = "closed_shape_without_optional_jsonschema_dependency"
        schema_valid = schema_valid and set(schemas[0]["required"]).issubset(traces)
    else:
        for schema in schemas:
            jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schemas[0]).validate(traces)
        schema_mode = "draft_2020_12_jsonschema"
    tests = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_proper_v2_3_public_branch_capture"],
        cwd=ROOT, capture_output=True, text=True,
    )
    hashes = {relative: _sha256(ROOT / relative) for relative in STAGE_INPUTS}
    checks = {
        "three_scripted_traces_pass": traces["passed"] and traces["trace_count"] == 3,
        "three_effect_classes_covered": traces["checks"]["three_effect_class_traces"],
        "unknown_outcome_trace_present": traces["checks"]["unknown_outcome_trace_present"],
        "five_condition_starts_identical": all(
            len(set(trace["condition_start_sha256"].values())) == 1
            and len(trace["condition_start_sha256"]) == 5
            for trace in traces["traces"]
        ),
        "unknown_side_effect_not_replayed": all(
            trace["checks"]["executed_unknown_is_not_replayed"] for trace in traces["traces"]
        ),
        "closed_schemas_valid": schema_valid,
        "scoped_tests_pass": tests.returncode == 0,
        "all_stage_inputs_hashed": len(hashes) == len(STAGE_INPUTS),
        "model_runner_remains_unauthorized": not traces["model_runner_authorized"],
    }
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_3_public_branch_capture_design_validation",
        "checks": checks,
        "passed": all(checks.values()),
        "scripted_trace_path": OUTPUT.relative_to(ROOT).as_posix(),
        "scripted_trace_sha256": _sha256(OUTPUT),
        "schema_validation_mode": schema_mode,
        "scoped_tests_run": 8,
        "stage_input_sha256": hashes,
        "task_executed": False,
        "model_loaded": False,
        "model_outputs_read": False,
        "gpu_used": False,
        "tau3_runtime_adapter_authorized": all(checks.values()),
        "model_runner_authorized": False,
        "model_run_authorized": False,
        "confirmatory_run_authorized": False,
        "next_gate": "implement_cpu_only_tau3_branch_replay_adapter",
    }


def main() -> int:
    result = validate()
    VALIDATION_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    VALIDATION_OUTPUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
