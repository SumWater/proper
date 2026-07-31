"""One-shot CPU-only validation for the first PROPER v2.3 stage."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import io
import json
import platform
import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
TESTS = ROOT / "tests"
EXPERIMENTS = ROOT / "experiments" / "proper_v2_3"
for path in (SRC, TESTS, EXPERIMENTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripted_traces_v2_3 import run_scripted_traces  # noqa: E402
from target_capacity_audit_v2_3 import validate_capacity_design  # noqa: E402

DEFAULT_OUTPUT = (
    ROOT / "outputs" / "proper_v2_3" / "first_stage_validation" / "results.json"
)

STAGE_SOURCE_PATHS = (
    "configs/proper_v2_3/execution_controller_v2_3.yaml",
    "configs/proper_v2_3/target_capacity_audit_v2_3.yaml",
    "docs/proper_v2_3/action_execution_contract.md",
    "docs/proper_v2_3/first_stage_index.md",
    "docs/proper_v2_3/target_capacity_audit_protocol.md",
    "schemas/proper_v2_3/action_execution_ledger.schema.json",
    "schemas/proper_v2_3/controller_decision.schema.json",
    "src/failure_memory/proper_v2/v2_3/__init__.py",
    "src/failure_memory/proper_v2/v2_3/boundary.py",
    "src/failure_memory/proper_v2/v2_3/contracts.py",
    "src/failure_memory/proper_v2/v2_3/ledger.py",
    "src/failure_memory/proper_v2/v2_3/controller.py",
    "experiments/proper_v2_3/scripted_traces_v2_3.py",
    "experiments/proper_v2_3/target_capacity_audit_v2_3.py",
    "experiments/proper_v2_3/validate_proper_v2_3_stage.py",
    "tests/test_proper_v2_3_contracts.py",
    "tests/test_proper_v2_3_controller.py",
    "tests/test_proper_v2_3_frozen_hashes.py",
    "tests/test_proper_v2_3_ledger.py",
    "tests/test_proper_v2_3_lifecycle_budgets.py",
    "tests/test_proper_v2_3_schemas.py",
    "tests/test_toolsandbox_v2_3_capacity_audit.py",
    "tests/test_toolsandbox_v2_3_scripted_traces.py",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_tests() -> dict[str, Any]:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite(
        (
            loader.discover(
                str(TESTS),
                pattern="test_proper_v2_3_*.py",
                top_level_dir=str(TESTS),
            ),
            loader.discover(
                str(TESTS),
                pattern="test_toolsandbox_v2_3_*.py",
                top_level_dir=str(TESTS),
            ),
        )
    )
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    return {
        "passed": result.wasSuccessful(),
        "tests_run": result.testsRun,
        "failure_count": len(result.failures),
        "error_count": len(result.errors),
        "skipped_count": len(result.skipped),
        "failures": [
            {"test": str(test), "traceback": traceback}
            for test, traceback in result.failures
        ],
        "errors": [
            {"test": str(test), "traceback": traceback}
            for test, traceback in result.errors
        ],
        "skipped": [
            {"test": str(test), "reason": reason}
            for test, reason in result.skipped
        ],
        "runner_output": stream.getvalue(),
    }


def _validate_json_artifacts() -> dict[str, Any]:
    paths = (
        ROOT / "configs/proper_v2_3/execution_controller_v2_3.yaml",
        ROOT / "configs/proper_v2_3/target_capacity_audit_v2_3.yaml",
        ROOT / "schemas/proper_v2_3/action_execution_ledger.schema.json",
        ROOT / "schemas/proper_v2_3/controller_decision.schema.json",
    )
    parsed = {}
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"expected object in {path}")
        parsed[str(path.relative_to(ROOT)).replace("\\", "/")] = True
    return {"passed": True, "parsed": parsed}


def _validation_environment() -> dict[str, Any]:
    try:
        jsonschema_version = importlib.metadata.version("jsonschema")
    except importlib.metadata.PackageNotFoundError:
        jsonschema_version = None
    return {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "jsonschema_version": jsonschema_version,
        "project_declared_jsonschema_version": "4.23.0",
        "project_declared_jsonschema_version_matched": (
            jsonschema_version == "4.23.0"
        ),
    }


def validate_stage() -> dict[str, Any]:
    test_result = _run_tests()
    traces = run_scripted_traces()
    capacity = validate_capacity_design()
    json_validation = _validate_json_artifacts()
    source_hashes = {
        relative: _sha256(ROOT / relative) for relative in STAGE_SOURCE_PATHS
    }
    passed = all(
        (
            test_result["passed"],
            traces["passed"],
            capacity["passed"],
            json_validation["passed"],
        )
    )
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_3_first_stage_cpu_validation",
        "passed": passed,
        "method_version": "proper_v2_3_execution_controller_development",
        "tests": test_result,
        "scripted_traces": {
            "passed": traces["passed"],
            "trace_count": traces["trace_count"],
            "passed_trace_count": traces["passed_trace_count"],
            "records": traces["traces"],
        },
        "target_capacity_design": capacity,
        "json_artifacts": json_validation,
        "validation_environment": _validation_environment(),
        "source_hashes": source_hashes,
        "boundary": {
            "model_runner_present": False,
            "model_loaded": False,
            "model_outputs_read": False,
            "target_scenarios_played": False,
            "gpu_used": False,
            "development_model_run_authorized": False,
            "confirmatory_claim_authorized": False,
        },
        "interpretation_limits": [
            "scripted_traces_are_not_model_behavior",
            "existing_12_pairs_remain_development_only",
            "no_new_target_capacity_is_currently_available",
            "no_final_task_completion_claim_is_authorized",
            "no_all_agent_memory_generalization_is_authorized",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = validate_stage()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(
        (
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n"
        ).encode("utf-8")
    )
    print(
        json.dumps(
            {
                "passed": result["passed"],
                "tests_run": result["tests"]["tests_run"],
                "scripted_traces": result["scripted_traces"]["trace_count"],
                "capacity_disposition": result["target_capacity_design"]["disposition"],
                "output": str(args.output),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
