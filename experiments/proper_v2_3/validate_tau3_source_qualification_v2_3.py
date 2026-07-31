"""One-shot CPU validation for the PROPER v2.3 tau3 source stage."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import io
import json
import subprocess
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

from tau3_source_qualification_v2_3 import qualify_source  # noqa: E402

DEFAULT_OUTPUT = (
    ROOT
    / "outputs"
    / "proper_v2_3"
    / "tau3_source_qualification"
    / "validation.json"
)
SCHEMA = ROOT / "schemas" / "proper_v2_3" / "source_qualification.schema.json"
FIRST_STAGE_RESULT = (
    ROOT
    / "outputs"
    / "proper_v2_3"
    / "first_stage_validation"
    / "results.json"
)
FIRST_STAGE_RESULT_SHA256 = (
    "7d17a69032e6f4fab8293b837ba8dd61484f2726ecf317a71d158c677d227056"
)
FIRST_STAGE_COMMIT = "c1d4b291ee34a2c041a7c10ff16aee56150ad2ee"

STAGE_SOURCE_PATHS = (
    "configs/proper_v2_3/tau3_source_qualification_v2_3.yaml",
    "docs/proper_v2_3/tau3_source_qualification_stage.md",
    "experiments/proper_v2_3/tau3_source_qualification_v2_3.py",
    "experiments/proper_v2_3/validate_tau3_source_qualification_v2_3.py",
    "schemas/proper_v2_3/source_qualification.schema.json",
    "tests/test_proper_v2_3_tau3_source_qualification.py",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_tests() -> dict[str, Any]:
    suite = unittest.defaultTestLoader.discover(
        str(TESTS),
        pattern="test_proper_v2_3_tau3_source_qualification.py",
        top_level_dir=str(TESTS),
    )
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    return {
        "passed": result.wasSuccessful(),
        "tests_run": result.testsRun,
        "failure_count": len(result.failures),
        "error_count": len(result.errors),
        "skipped_count": len(result.skipped),
        "runner_output": stream.getvalue(),
    }


def _validate_schema(audit: dict[str, Any]) -> dict[str, Any]:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    try:
        import jsonschema
    except ImportError:
        return {
            "passed": True,
            "validator": "structural_fallback_no_jsonschema",
            "draft_2020_12_validation_performed": False,
            "schema_is_object": isinstance(schema, dict),
            "audit_is_object": isinstance(audit, dict),
        }
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(audit)
    return {
        "passed": True,
        "validator": f"jsonschema_{importlib.metadata.version('jsonschema')}",
        "draft_2020_12_validation_performed": True,
    }


def _first_stage_frozen() -> dict[str, Any]:
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", FIRST_STAGE_COMMIT, "HEAD"],
        cwd=ROOT,
        check=False,
    ).returncode == 0
    actual_hash = _sha256(FIRST_STAGE_RESULT)
    return {
        "passed": ancestor and actual_hash == FIRST_STAGE_RESULT_SHA256,
        "commit": FIRST_STAGE_COMMIT,
        "commit_is_ancestor": ancestor,
        "first_stage_result_sha256": actual_hash,
        "first_stage_result_hash_matches": actual_hash == FIRST_STAGE_RESULT_SHA256,
    }


def validate_stage() -> dict[str, Any]:
    audit = qualify_source()
    tests = _run_tests()
    schema = _validate_schema(audit)
    first_stage = _first_stage_frozen()
    source_hashes = {
        relative: _sha256(ROOT / relative) for relative in STAGE_SOURCE_PATHS
    }
    passed = all(
        (audit["passed"], tests["passed"], schema["passed"], first_stage["passed"])
    )
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_3_tau3_source_qualification_stage_validation",
        "passed": passed,
        "source_qualification": audit,
        "tests": tests,
        "schema_validation": schema,
        "first_stage_frozen": first_stage,
        "source_hashes": source_hashes,
        "boundary": {
            "model_loaded": False,
            "model_outputs_read": False,
            "target_tasks_executed": False,
            "gpu_used": False,
            "new_target_capacity_available": False,
            "development_model_run_authorized": False,
            "confirmatory_run_authorized": False,
        },
        "next_gate": "cpu_scripted_recoverable_branch_validation",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = validate_stage()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(
        (
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
    )
    print(
        json.dumps(
            {
                "passed": result["passed"],
                "tests_run": result["tests"]["tests_run"],
                "source_disposition": result["source_qualification"]["disposition"],
                "new_target_capacity_available": result["boundary"][
                    "new_target_capacity_available"
                ],
                "next_gate": result["next_gate"],
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
