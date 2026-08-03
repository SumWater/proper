"""Validate acquisition runtime implementation using synthetic CPU I/O only."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/proper_v2_3/acquisition_runtime_implementation_v2_3.json"
DRY_SCHEMA = ROOT / "schemas/proper_v2_3/acquisition_runtime_synthetic_dry_run.schema.json"
VALIDATION_SCHEMA = ROOT / "schemas/proper_v2_3/acquisition_runtime_implementation_validation.schema.json"
OUTPUT_DIR = ROOT / "outputs/proper_v2_3/acquisition_runtime_implementation"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.proper_v2_3.run_acquisition_runtime_synthetic_cpu_v2_3 import run as run_dry


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _top_level_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            result.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module.split(".")[0])
    return result


def validate() -> tuple[dict[str, Any], dict[str, Any]]:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    protocol = config["protocol"]
    implementation_hashes_match = all(
        _sha256(ROOT / item["path"]) == item["sha256"]
        for item in config["implementation_inputs"]
    )
    protocol_hashes_match = (
        _sha256(ROOT / protocol["path"]) == protocol["sha256"]
        and _sha256(ROOT / protocol["validation_path"]) == protocol["validation_sha256"]
    )
    tests = subprocess.run(
        [
            sys.executable, "-W", "error::ResourceWarning", "-m", "unittest",
            "tests.test_proper_v2_3_acquisition_runtime",
        ],
        cwd=ROOT, capture_output=True, text=True,
    )
    dry = run_dry()
    dry_bytes = (json.dumps(dry, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    dry_schema = json.loads(DRY_SCHEMA.read_text(encoding="utf-8"))
    implementation_paths = [ROOT / item["path"] for item in config["implementation_inputs"]]
    top_imports = set().union(*(_top_level_imports(path) for path in implementation_paths[:-1]))
    corrections = config["pre_model_corrections_to_protocol_v1_simulator"]
    deliberate = dry["deliberate_failures"]
    gates = config["gates"]
    checks = {
        "frozen_protocol_and_validation_unchanged": protocol_hashes_match,
        "all_declared_implementation_hashes_match": implementation_hashes_match,
        "eleven_scoped_runtime_tests_pass_without_resource_warnings": tests.returncode == 0,
        "fifteen_synthetic_end_to_end_checks_pass": dry["passed"] and len(dry["checks"]) == 15,
        "synthetic_output_matches_closed_schema_fields": set(dry) == set(dry_schema["required"]),
        "three_effect_class_captures_pass": dry["successful_stage"]["captured"] == 3,
        "invalid_output_and_worker_failure_are_preserved": deliberate["invalid_output"]["public_state"]["failure_reason"] == "invalid_agent_output" and deliberate["worker_error"]["public_state"]["status"] == "infrastructure_failure",
        "ambiguous_and_duplicate_writes_stop_closed": deliberate["ambiguous_non_target_write"]["public_state"]["failure_reason"] == "ambiguous_non_target_tool_outcome" and deliberate["duplicate_state_change"]["public_state"]["status"] == "safety_failure",
        "both_pre_model_protocol_corrections_exercised": len(corrections) == 2 and dry["checks"]["pre_action_uses_actual_environment_checkpoint"] and dry["checks"]["ambiguous_non_target_write_stops_with_checkpoint"],
        "no_top_level_tau_or_model_library_import": not (top_imports & {"tau2","torch","transformers","accelerate"}),
        "private_scenario_evaluator_and_policy_boundaries_hold": dry["checks"]["agent_never_receives_private_scenario"] and dry["checks"]["user_never_receives_domain_policy"] and dry["checks"]["worker_messages_exclude_evaluator_pair_ids"],
        "all_outputs_are_explicitly_synthetic": dry["checks"]["all_worker_outputs_are_synthetic"] and dry["tau_imported"] is False,
        "model_task_capture_gpu_gates_remain_closed": not any((
            gates["real_runner_implemented"], gates["model_loading_authorized"],
            gates["task_execution_authorized"], gates["real_branch_capture_authorized"],
            gates["comparison_runner_authorized"], gates["gpu_authorized"],
            gates["confirmatory_claim_authorized"],
        )),
    }
    passed = all(checks.values())
    validation_inputs = (
        "configs/proper_v2_3/acquisition_runtime_implementation_v2_3.json",
        "src/failure_memory/proper_v2/v2_3/acquisition_runtime.py",
        "src/failure_memory/proper_v2/v2_3/tau3_acquisition_runtime_adapter.py",
        "experiments/proper_v2_3/synthetic_acquisition_jsonl_worker_v2_3.py",
        "experiments/proper_v2_3/run_acquisition_runtime_synthetic_cpu_v2_3.py",
        "tests/test_proper_v2_3_acquisition_runtime.py",
        "schemas/proper_v2_3/acquisition_runtime_synthetic_dry_run.schema.json",
        "schemas/proper_v2_3/acquisition_runtime_implementation_validation.schema.json",
    )
    result = {
        "schema_version":1,
        "run_kind":"proper_v2_3_acquisition_runtime_implementation_validation",
        "implementation_config_sha256":_sha256(CONFIG),
        "protocol_validation_sha256":_sha256(ROOT / protocol["validation_path"]),
        "synthetic_dry_run_sha256":hashlib.sha256(dry_bytes).hexdigest(),
        "validation_input_sha256":{path:_sha256(ROOT / path) for path in validation_inputs},
        "checks":checks,
        "passed":passed,
        "scoped_tests_run":11,
        "synthetic_checks_run":len(dry["checks"]),
        "model_loaded":False,
        "model_outputs_read":False,
        "tau_imported":False,
        "task_executed":False,
        "gpu_used":False,
        "one_shot_runner_protocol_design_authorized":passed,
        "real_runner_implemented":False,
        "model_loading_authorized":False,
        "real_branch_capture_authorized":False,
        "confirmatory_run_authorized":False,
        "next_gate":"freeze_one_shot_acquisition_runner_protocol" if passed else "stop_runtime_implementation",
    }
    schema = json.loads(VALIDATION_SCHEMA.read_text(encoding="utf-8"))
    checks["validation_output_matches_closed_schema_fields"] = set(result) == set(schema["required"])
    result["passed"] = all(checks.values())
    result["one_shot_runner_protocol_design_authorized"] = result["passed"]
    result["next_gate"] = "freeze_one_shot_acquisition_runner_protocol" if result["passed"] else "stop_runtime_implementation"
    return result, dry


def main() -> int:
    result, dry = validate()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "synthetic_dry_run.json").write_bytes((json.dumps(dry, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    (OUTPUT_DIR / "validation.json").write_bytes((json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
