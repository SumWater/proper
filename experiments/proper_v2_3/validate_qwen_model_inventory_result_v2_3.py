"""Freeze returned Qwen inventory results without reading model files."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/proper_v2_3/qwen_model_inventory_freeze_v2_3.json"
REMOTE_SCHEMA = ROOT / "schemas/proper_v2_3/qwen_model_inventory.schema.json"
FREEZE_SCHEMA = ROOT / "schemas/proper_v2_3/qwen_model_inventory_freeze.schema.json"
OUTPUT = ROOT / "outputs/proper_v2_3/qwen_model_inventory_freeze/validation.json"
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def inventory_shape_errors(result: Mapping[str, Any], required: set[str]) -> list[str]:
    errors: list[str] = []
    if set(result) != required:
        errors.append("closed_top_level_fields")
    files = result.get("files")
    if not isinstance(files, list):
        return errors + ["files_not_array"]
    paths: list[str] = []
    total = 0
    for item in files:
        if not isinstance(item, Mapping) or set(item) != {"relative_path", "size_bytes", "sha256"}:
            errors.append("invalid_file_record")
            continue
        relative = item["relative_path"]
        pure = PurePosixPath(relative) if isinstance(relative, str) else PurePosixPath("/")
        if pure.is_absolute() or ".." in pure.parts or "\\" in str(relative):
            errors.append("unsafe_relative_path")
        paths.append(str(relative))
        if not isinstance(item["size_bytes"], int) or isinstance(item["size_bytes"], bool) or item["size_bytes"] < 0:
            errors.append("invalid_size")
        else:
            total += item["size_bytes"]
        if not isinstance(item["sha256"], str) or not SHA256.fullmatch(item["sha256"]):
            errors.append("invalid_file_sha256")
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        errors.append("paths_not_sorted_unique")
    if result.get("file_count") != len(files):
        errors.append("file_count_mismatch")
    if result.get("total_bytes") != total:
        errors.append("total_bytes_mismatch")
    expected_manifest = _canonical_sha256(files) if files else None
    if result.get("manifest_sha256") != expected_manifest:
        errors.append("manifest_mismatch")
    return errors


def validate() -> dict[str, Any]:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    schema = json.loads(REMOTE_SCHEMA.read_text(encoding="utf-8"))
    required = set(schema["required"])
    records = []
    actual_hashes: dict[str, str] = {}
    for declared in config["remote_results"]:
        path = ROOT / declared["path"]
        records.append((declared, json.loads(path.read_text(encoding="utf-8"))))
        actual_hashes[declared["path"]] = _sha256(path)
    failures = [item for declared, item in records if declared["expected_outcome"] == "preflight_failed"]
    successes = [item for declared, item in records if declared["expected_outcome"] == "passed"]
    success = successes[0] if len(successes) == 1 else {}
    expected = config["successful_inventory"]
    shape_errors = [inventory_shape_errors(item, required) for _, item in records]
    checks = {
        "all_three_results_present_and_hashed": len(records) == 3 and all(
            actual_hashes[item["path"]] == item["sha256"] for item in config["remote_results"]
        ),
        "remote_results_match_closed_schema_shape": not any(shape_errors),
        "two_preflight_failures_preserved": len(failures) == 2 and all(
            not item["passed"] and item["stop_reason"] == "preflight_failed"
            and not item["checks"]["tracked_worktree_clean"] and item["file_count"] == 0
            for item in failures
        ),
        "successful_inventory_unique": len(successes) == 1 and bool(success.get("passed")),
        "successful_revision_and_config_match": success.get("project_revision") == expected["project_revision"]
            and success.get("config_sha256") == expected["config_sha256"],
        "successful_counts_match": success.get("file_count") == expected["file_count"]
            and success.get("total_bytes") == expected["total_bytes"],
        "successful_manifest_recomputed": success.get("manifest_sha256") == expected["manifest_sha256"]
            and success.get("manifest_sha256") == _canonical_sha256(success.get("files", [])),
        "successful_runtime_gates_closed": all(
            not success.get(key) for key in (
                "model_loaded", "model_outputs_read", "task_executed", "gpu_used",
                "acquisition_runtime_freeze_authorized", "real_branch_capture_authorized",
                "model_runner_authorized", "confirmatory_run_authorized",
            )
        ),
    }
    tests = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_proper_v2_3_qwen_model_inventory_result"],
        cwd=ROOT, capture_output=True, text=True,
    )
    checks["four_local_freeze_tests_pass"] = tests.returncode == 0
    result = {
        "schema_version": 1,
        "run_kind": "proper_v2_3_qwen_model_inventory_local_freeze",
        "checks": checks,
        "passed": False,
        "remote_result_sha256": actual_hashes,
        "successful_manifest_sha256": str(success.get("manifest_sha256") or ""),
        "successful_file_count": int(success.get("file_count") or 0),
        "successful_total_bytes": int(success.get("total_bytes") or 0),
        "preserved_preflight_failures": len(failures),
        "model_loaded": False,
        "model_outputs_read": False,
        "task_executed": False,
        "gpu_used": False,
        "acquisition_runtime_protocol_design_authorized": False,
        "acquisition_runtime_freeze_authorized": False,
        "real_branch_capture_authorized": False,
        "model_runner_authorized": False,
        "confirmatory_run_authorized": False,
        "next_gate": "stop_inventory_freeze",
    }
    freeze_required = set(json.loads(FREEZE_SCHEMA.read_text(encoding="utf-8"))["required"])
    checks["local_freeze_envelope_matches_schema_fields"] = set(result) == freeze_required
    passed = all(checks.values())
    result["passed"] = passed
    result["acquisition_runtime_protocol_design_authorized"] = passed
    result["next_gate"] = "design_acquisition_runtime_protocol" if passed else "stop_inventory_freeze"
    return result


def main() -> int:
    result = validate()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
