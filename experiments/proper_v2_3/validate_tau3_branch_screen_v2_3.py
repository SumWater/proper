"""One-shot CPU validation for the frozen tau3 development branch screen."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import io
import json
import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS = ROOT / "experiments" / "proper_v2_3"
TESTS = ROOT / "tests"
for path in (EXPERIMENTS, TESTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from tau3_branch_screen_v2_3 import DEFAULT_CONFIG, DEFAULT_OUTPUT, run

VALIDATION_OUTPUT = ROOT / "outputs" / "proper_v2_3" / "tau3_branch_screen" / "validation.json"
SCHEMA = ROOT / "schemas" / "proper_v2_3" / "tau3_branch_screen.schema.json"
STAGE_SOURCE_PATHS = (
    "configs/proper_v2_3/tau3_branch_screen_v2_3.yaml",
    "docs/proper_v2_3/tau3_branch_screen_stage.md",
    "experiments/proper_v2_3/tau3_branch_screen_v2_3.py",
    "experiments/proper_v2_3/validate_tau3_branch_screen_v2_3.py",
    "schemas/proper_v2_3/tau3_branch_screen.schema.json",
    "tests/test_proper_v2_3_tau3_branch_screen.py",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_tests() -> dict[str, Any]:
    suite = unittest.defaultTestLoader.discover(str(TESTS), pattern="test_*v2_3*.py", top_level_dir=str(TESTS))
    stream = io.StringIO(); result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    return {"passed": result.wasSuccessful(), "tests_run": result.testsRun,
            "failure_count": len(result.failures), "error_count": len(result.errors),
            "skipped_count": len(result.skipped), "runner_output": stream.getvalue()}


def validate_schema(result: dict[str, Any]) -> dict[str, Any]:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    try:
        import jsonschema
    except ImportError:
        required = set(schema["required"])
        return {"passed": required.issubset(result), "validator": "structural_fallback_no_jsonschema",
                "draft_2020_12_validation_performed": False}
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(result)
    return {"passed": True, "validator": f"jsonschema_{importlib.metadata.version('jsonschema')}",
            "draft_2020_12_validation_performed": True}


def validate(dependency_dir: Path | None) -> dict[str, Any]:
    result = run(DEFAULT_CONFIG, DEFAULT_OUTPUT, dependency_dir)
    tests = run_tests(); schema = validate_schema(result)
    passed = result["passed"] and tests["passed"] and schema["passed"]
    return {
        "schema_version": 1, "run_kind": "proper_v2_3_tau3_branch_screen_stage_validation",
        "passed": passed, "branch_screen": result, "tests": tests, "schema_validation": schema,
        "source_hashes": {path: sha256(ROOT / path) for path in STAGE_SOURCE_PATHS},
        "generated_result_sha256": sha256(DEFAULT_OUTPUT),
        "boundary": {"model_loaded": False, "gpu_used": False, "target_tasks_executed": False,
                     "qualified_development_pair_count": result["summary"]["qualified_development_pair_count"],
                     "new_heldout_target_capacity": 0, "development_model_run_authorized": False,
                     "confirmatory_run_authorized": False},
        "next_gate": result["next_gate"] if passed else "stop_and_preserve_negative_branch_screen",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dependency-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=VALIDATION_OUTPUT)
    args = parser.parse_args(); result = validate(args.dependency_dir.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(
        (json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    )
    print(json.dumps({"passed": result["passed"], "tests_run": result["tests"]["tests_run"],
                      "qualified_development_pair_count": result["boundary"]["qualified_development_pair_count"],
                      "new_heldout_target_capacity": 0, "next_gate": result["next_gate"],
                      "output": str(args.output)}, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
