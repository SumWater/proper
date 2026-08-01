"""One-shot CPU validation for the frozen v2.3 five-condition preparation."""

from __future__ import annotations

import argparse
import importlib.metadata
import io
import json
import os
import platform
import re
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS = ROOT / "experiments" / "proper_v2_3"
if str(EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS))

from prepare_five_condition_development_v2_3 import (  # noqa: E402
    DEFAULT_CONFIG, load_object, prepare, sha256, write_result,
)

MANIFEST_SCHEMA = ROOT / "schemas" / "proper_v2_3" / "five_condition_manifest.schema.json"
VALIDATION_SCHEMA = ROOT / "schemas" / "proper_v2_3" / "five_condition_preparation_validation.schema.json"


def git(*args: str, directory: Path = ROOT) -> str:
    completed = subprocess.run(
        ["git", "-C", str(directory), *args], capture_output=True, text=True,
        encoding="utf-8", check=True,
    )
    return completed.stdout.strip()


def verify_preconditions(config: Mapping[str, Any], expected_revision: str) -> dict[str, Any]:
    policy = config["remote_preparation_validation"]
    if os.environ.get("PROPER_V2_3_EXECUTION_ROLE") != policy["execution_role"]:
        raise RuntimeError("five-condition remote execution role is missing")
    if os.environ.get("CUDA_VISIBLE_DEVICES") != policy["cuda_visible_devices"]:
        raise RuntimeError("CPU-only CUDA guard is missing")
    if sys.version_info.major != 3 or sys.version_info.minor not in policy["allowed_python_minors"]:
        raise RuntimeError(f"unsupported Python version: {platform.python_version()}")
    if not re.fullmatch(r"[0-9a-f]{40}", expected_revision):
        raise RuntimeError("expected project revision must be a full Git commit")
    head = git("rev-parse", "HEAD")
    if head != expected_revision:
        raise RuntimeError(f"project revision mismatch: expected {expected_revision}, got {head}")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", policy["required_project_ancestor"], head],
        cwd=ROOT, check=False,
    ).returncode == 0
    if not ancestor:
        raise RuntimeError("required five-condition protocol commit is not an ancestor")
    tracked_status = git("status", "--porcelain", "--untracked-files=no")
    if tracked_status:
        raise RuntimeError("tracked project worktree must be clean")
    tau_head = git("rev-parse", "HEAD", directory=ROOT / policy["tau_directory"])
    if tau_head != policy["tau_revision"]:
        raise RuntimeError("pinned tau revision mismatch")
    return {
        "execution_role": policy["execution_role"], "project_revision": head,
        "required_ancestor_present": ancestor, "tracked_worktree_clean": not tracked_status,
        "tau_revision": tau_head, "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "python_version": platform.python_version(),
    }


def run_tests(config: Mapping[str, Any]) -> dict[str, Any]:
    policy = config["preparation_test_policy"]
    suite = unittest.TestSuite()
    tests = ROOT / "tests"
    for pattern in policy["patterns"]:
        suite.addTests(unittest.defaultTestLoader.discover(
            str(tests), pattern=pattern, top_level_dir=str(tests)
        ))
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    count_matches = result.testsRun == policy["expected_test_count"]
    return {
        "passed": result.wasSuccessful() and count_matches,
        "patterns": policy["patterns"],
        "expected_test_count": policy["expected_test_count"],
        "tests_run": result.testsRun,
        "test_count_matches_contract": count_matches,
        "failures": len(result.failures), "errors": len(result.errors),
        "skipped": len(result.skipped), "runner_output": stream.getvalue(),
    }


def validate_manifest(value: Mapping[str, Any]) -> dict[str, Any]:
    import jsonschema

    schema = load_object(MANIFEST_SCHEMA)
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(value)
    return {"passed": True, "draft": "2020-12",
            "validator": f"jsonschema_{importlib.metadata.version('jsonschema')}"}


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--expected-project-revision", required=True)
    args = parser.parse_args()
    config_path = args.config.resolve()
    config = load_object(config_path)
    preconditions = verify_preconditions(config, args.expected_project_revision)
    manifest_path = ROOT / config["output"]["prepared_manifest"]
    validation_path = ROOT / config["output"]["validation"]
    for path in (manifest_path, validation_path):
        if path.exists() and config["output"]["never_overwrite"]:
            raise FileExistsError(f"refusing to overwrite frozen preparation artifact: {path}")
    manifest = prepare(config_path)
    write_result(manifest, manifest_path)
    schema_result = validate_manifest(manifest)
    tests = run_tests(config)
    passed = manifest["status"] == "passed" and schema_result["passed"] and tests["passed"]
    validation = {
        "schema_version": 1,
        "run_kind": "proper_v2_3_five_condition_preparation_validation",
        "passed": passed,
        "preconditions": preconditions,
        "prepared_manifest_path": manifest_path.relative_to(ROOT).as_posix(),
        "prepared_manifest_sha256": sha256(manifest_path),
        "manifest_schema_validation": schema_result,
        "tests": tests,
        "boundary": {
            "model_runner_implemented": False, "model_loaded": False,
            "gpu_used": False, "target_scenarios_played": False,
            "development_model_run_authorized": False,
            "confirmatory_claim_authorized": False,
            "new_heldout_target_capacity": 0,
        },
        "next_gate": config["next_gate_on_pass"] if passed else config["next_gate_on_failure"],
    }
    write_json(validation_path, validation)
    import jsonschema
    validation_schema = load_object(VALIDATION_SCHEMA)
    jsonschema.Draft202012Validator.check_schema(validation_schema)
    jsonschema.Draft202012Validator(validation_schema).validate(validation)
    print(json.dumps({"passed": passed, "tests_run": tests["tests_run"],
                      "conditions": config["cohort"]["total_condition_count"],
                      "model_run_authorized": False,
                      "next_gate": validation["next_gate"],
                      "output": str(validation_path)}, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
