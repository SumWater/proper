"""Remote-only CPU execution envelope for the PROPER v2.3 tau3 screen."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import io
import json
import os
import platform
import re
import subprocess
import sys
import traceback
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS = ROOT / "experiments" / "proper_v2_3"
for path in (ROOT / "src", EXPERIMENTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from tau3_branch_screen_v2_3 import DEFAULT_CONFIG, load_object, run, sha256

REMOTE_CONFIG = ROOT / "configs" / "proper_v2_3" / "tau3_remote_execution_v2_3.yaml"
REMOTE_SCHEMA = ROOT / "schemas" / "proper_v2_3" / "tau3_remote_execution.schema.json"


def git(*args: str, directory: Path = ROOT, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", "-C", str(directory), *args], capture_output=True, text=True,
        encoding="utf-8", check=check,
    )
    return completed.stdout.strip()


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def verify_preconditions(config: Mapping[str, Any], expected_revision: str) -> dict[str, Any]:
    actual_role = os.environ.get("PROPER_V2_3_EXECUTION_ROLE")
    if actual_role != config["execution_role"]:
        raise RuntimeError("remote execution role was not explicitly declared")
    required_python = config["python"]
    if sys.version_info[:2] != (required_python["required_major"], required_python["required_minor"]):
        raise RuntimeError(f"Python 3.12 is required, got {platform.python_version()}")
    if os.environ.get("CUDA_VISIBLE_DEVICES") != config["runtime_guards"]["cuda_visible_devices"]:
        raise RuntimeError("CPU-only CUDA guard is missing")
    head = git("rev-parse", "HEAD")
    if not re.fullmatch(r"[0-9a-f]{40}", expected_revision):
        raise RuntimeError("expected project revision must be a full 40-character Git commit")
    if head != expected_revision:
        raise RuntimeError(f"project revision mismatch: expected {expected_revision}, got {head}")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", config["project"]["required_ancestor"], head],
        cwd=ROOT, check=False,
    ).returncode == 0
    if not ancestor:
        raise RuntimeError("required frozen branch-screen commit is not an ancestor")
    tracked_status = git("status", "--porcelain", "--untracked-files=no")
    if tracked_status:
        raise RuntimeError("tracked project worktree must be clean")
    tau = ROOT / config["tau_source"]["directory"]
    tau_head = git("rev-parse", "HEAD", directory=tau)
    if tau_head != config["tau_source"]["revision"]:
        raise RuntimeError("pinned tau source revision mismatch")
    return {
        "execution_role": actual_role,
        "project_revision": head,
        "required_ancestor_present": ancestor,
        "tracked_worktree_clean": not tracked_status,
        "tau_revision": tau_head,
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
    }


def source_manifest(config: Mapping[str, Any]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for relative_root in config["sync_roots"]:
        directory = ROOT / relative_root
        for path in sorted(item for item in directory.rglob("*") if item.is_file()):
            relative = path.relative_to(ROOT).as_posix()
            if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
                continue
            records.append({"path": relative, "bytes": path.stat().st_size, "sha256": sha256(path)})
    return {"file_count": len(records), "bytes": sum(item["bytes"] for item in records),
            "manifest_sha256": canonical_sha256(records), "records": records}


def resolved_packages() -> list[dict[str, str]]:
    return sorted(
        ({"name": distribution.metadata["Name"], "version": distribution.version}
         for distribution in importlib.metadata.distributions() if distribution.metadata["Name"]),
        key=lambda item: item["name"].lower(),
    )


def run_repository_tests(config: Mapping[str, Any]) -> dict[str, Any]:
    policy = config["test_policy"]
    suite = unittest.defaultTestLoader.discover(
        str(ROOT / policy["discovery_start"]), pattern=policy["pattern"], top_level_dir=str(ROOT / policy["discovery_start"])
    )
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    return {"passed": result.wasSuccessful(), "tests_run": result.testsRun,
            "failure_count": len(result.failures), "error_count": len(result.errors),
            "skipped_count": len(result.skipped), "runner_output": stream.getvalue()}


def validate_branch_schema(branch_result: Mapping[str, Any]) -> dict[str, Any]:
    import jsonschema

    schema_path = ROOT / "schemas" / "proper_v2_3" / "tau3_branch_screen.schema.json"
    schema = load_object(schema_path)
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(branch_result)
    return {"passed": True, "draft_2020_12_validation_performed": True,
            "validator": f"jsonschema_{importlib.metadata.version('jsonschema')}"}


def safe_host_token() -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", platform.node()).strip("-").lower()
    return normalized or "unnamed-host"


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def execute_remote(expected_revision: str) -> tuple[Path, dict[str, Any]]:
    config = load_object(REMOTE_CONFIG)
    preconditions = verify_preconditions(config, expected_revision)
    started = datetime.now(timezone.utc)
    run_id = f"{started.strftime('%Y%m%dT%H%M%SZ')}-{safe_host_token()}-{expected_revision[:12]}"
    output_root = (ROOT / config["remote_outputs"]["root"]).resolve()
    run_directory = output_root / run_id
    run_directory.mkdir(parents=True, exist_ok=False)
    raw_path = run_directory / config["remote_outputs"]["raw_result_name"]
    envelope_path = run_directory / config["remote_outputs"]["envelope_name"]
    manifest = source_manifest(config)
    branch_result: dict[str, Any] | None = None
    schema_result: dict[str, Any] = {"passed": False, "not_run_reason": "branch_screen_not_completed"}
    tests: dict[str, Any] = {"passed": False, "tests_run": 0, "not_run_reason": "branch_screen_not_completed"}
    execution_error: dict[str, str] | None = None
    try:
        branch_result = run(DEFAULT_CONFIG, raw_path, None)
        schema_result = validate_branch_schema(branch_result)
        tests = run_repository_tests(config)
    except Exception as exc:  # Preserve negative remote evidence before returning failure.
        execution_error = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
    finished = datetime.now(timezone.utc)
    gates = config["formal_pass_gates"]
    passed = bool(
        execution_error is None and branch_result is not None
        and branch_result.get("passed") is gates["branch_screen_passed"]
        and schema_result.get("passed") is gates["schema_validation_passed"]
        and tests.get("passed") is gates["all_repository_tests_passed"]
        and branch_result["summary"]["qualified_development_pair_count"] == gates["qualified_development_pair_count"]
        and branch_result["summary"]["new_heldout_target_capacity"] == gates["new_heldout_target_capacity"]
        and branch_result["summary"]["development_model_run_authorized"] is gates["development_model_run_authorized"]
        and branch_result["summary"]["confirmatory_claim_authorized"] is gates["confirmatory_run_authorized"]
    )
    envelope: dict[str, Any] = {
        "schema_version": 1, "run_kind": "proper_v2_3_remote_formal_cpu_branch_screen",
        "run_id": run_id, "passed": passed, "scientific_scope": config["scientific_scope"],
        "started_at_utc": started.isoformat(), "finished_at_utc": finished.isoformat(),
        "duration_seconds": round((finished - started).total_seconds(), 6),
        "preconditions": preconditions,
        "host": {"node": platform.node(), "platform": platform.platform(),
                 "python_executable": sys.executable, "python_version": platform.python_version()},
        "resolved_packages": resolved_packages(), "source_manifest": manifest,
        "branch_result_path": raw_path.relative_to(ROOT).as_posix(),
        "branch_result_sha256": sha256(raw_path) if raw_path.is_file() else None,
        "branch_summary": branch_result.get("summary") if branch_result else None,
        "schema_validation": schema_result, "repository_tests": tests,
        "execution_error": execution_error,
        "boundary": {"local_self_test_is_formal_evidence": False, "remote_cpu_development_evidence": True,
                     "model_loaded": False, "gpu_used": False, "target_tasks_executed": False,
                     "new_heldout_target_capacity": 0, "development_model_run_authorized": False,
                     "confirmatory_run_authorized": False},
        "next_gate": config["next_gate_on_pass"] if passed else config["next_gate_on_failure"],
    }
    write_json(envelope_path, envelope)
    return envelope_path, envelope


def validate_envelope(path: Path, envelope: Mapping[str, Any]) -> None:
    import jsonschema

    schema = load_object(REMOTE_SCHEMA)
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(envelope)
    if load_object(path) != envelope:
        raise RuntimeError("persisted remote envelope does not match the validated value")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-project-revision", required=True)
    args = parser.parse_args()
    path, envelope = execute_remote(args.expected_project_revision)
    validate_envelope(path, envelope)
    print(json.dumps({"passed": envelope["passed"], "run_id": envelope["run_id"],
                      "tests_run": envelope["repository_tests"]["tests_run"],
                      "new_heldout_target_capacity": 0, "next_gate": envelope["next_gate"],
                      "output": str(path)}, sort_keys=True))
    return 0 if envelope["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
