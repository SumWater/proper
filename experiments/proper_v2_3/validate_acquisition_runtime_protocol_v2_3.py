"""CPU-only validation for the frozen acquisition-runtime protocol design."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/proper_v2_3/acquisition_runtime_protocol_v2_3.json"
REGISTRY = ROOT / "configs/proper_v2_3/tau3_acquisition_action_effects_v2_3.json"
SCHEMA = ROOT / "schemas/proper_v2_3/acquisition_runtime_protocol_validation.schema.json"
OUTPUT_DIR = ROOT / "outputs/proper_v2_3/acquisition_runtime_protocol"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.proper_v2_3.scripted_acquisition_runtime_protocol_v2_3 import run_traces


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _decorated_tools(path: Path) -> dict[str, str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or not decorator.args:
                continue
            if not isinstance(decorator.func, ast.Name) or decorator.func.id != "is_tool":
                continue
            argument = decorator.args[0]
            if isinstance(argument, ast.Attribute):
                result[node.name] = argument.attr
    return result


def _task_hashes(task: Mapping[str, Any]) -> dict[str, str]:
    return {
        "full_task_sha256": _canonical_sha256(task),
        "user_scenario_sha256": _canonical_sha256(task["user_scenario"]),
        "initial_state_sha256": _canonical_sha256(task["initial_state"]),
        "evaluator_only_sha256": _canonical_sha256(task["evaluation_criteria"]),
    }


def validate() -> tuple[dict[str, Any], dict[str, Any]]:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    frozen_inputs_match = all(_sha256(ROOT / item["path"]) == item["sha256"] for item in config["frozen_inputs"])

    source_root = ROOT / "external/tau2-bench"
    source_hashes_match = True
    tasks_by_domain: dict[str, dict[str, Mapping[str, Any]]] = {}
    for domain, expected in config["source_runtime"]["domains"].items():
        base = source_root / f"data/tau2/domains/{domain}"
        source_hashes_match &= (
            _sha256(base / "tasks.json") == expected["tasks_file_sha256"]
            and _sha256(base / "policy.md") == expected["policy_sha256"]
            and _sha256(base / "db.json") == expected["database_sha256"]
        )
        tasks = json.loads((base / "tasks.json").read_text(encoding="utf-8"))
        tasks_by_domain[domain] = {str(item["id"]): item for item in tasks}
    guidelines = source_root / "data/tau2/user_simulator/simulation_guidelines.md"
    source_hashes_match &= _sha256(guidelines) == config["source_runtime"]["user_simulation_guidelines_sha256"]

    task_hashes_match = True
    for item in config["task_hashes"]:
        actual = _task_hashes(tasks_by_domain[item["domain"]][item["source_task_id"]])
        task_hashes_match &= all(actual[key] == item[key] for key in actual)

    tool_contracts_complete = True
    public_tool_count = 0
    for domain, contracts in registry["contracts"].items():
        declared = _decorated_tools(source_root / f"src/tau2/domains/{domain}/tools.py")
        contracted = {item["action_name"]: item for item in contracts}
        public_tool_count += len(contracted)
        tool_contracts_complete &= set(declared) == set(contracted)
        for name, item in contracted.items():
            expected_types = {"READ", "GENERIC"} if item["effect_class"] == "read_only" else {"WRITE", "GENERIC"}
            tool_contracts_complete &= declared.get(name) in expected_types

    tests = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_proper_v2_3_acquisition_runtime_protocol"],
        cwd=ROOT, capture_output=True, text=True,
    )
    traces = run_traces()
    trace_bytes = (json.dumps(traces, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    trace_sha256 = hashlib.sha256(trace_bytes).hexdigest()
    separation = config["separation"]
    gates = config["gates"]
    checks = {
        "all_declared_frozen_input_hashes_match": frozen_inputs_match,
        "tau_source_policy_database_and_guideline_hashes_match": source_hashes_match,
        "all_twelve_task_component_hashes_match": task_hashes_match and len(config["task_hashes"]) == 12,
        "capture_order_matches_task_hash_order": config["capture_order"] == [item["pair_id"] for item in config["task_hashes"]],
        "all_thirty_public_tools_have_effect_contracts": tool_contracts_complete and public_tool_count == 30,
        "scripted_runtime_traces_pass": traces["passed"],
        "twelve_scoped_state_machine_tests_pass": tests.returncode == 0,
        "invalid_outputs_and_worker_errors_have_zero_retry": config["turn_loop"]["invalid_json_retry_count"] == 0 and config["turn_loop"]["worker_restart_count"] == 0,
        "budgets_are_independent": config["budgets"]["budgets_are_independent"],
        "evaluator_fields_excluded_from_worker_messages": not any((
            separation["task_id_in_worker_messages"], separation["gold_action_in_worker_messages"],
            separation["recoverability_in_worker_messages"], separation["evaluator_outcome_in_worker_messages"],
        )),
        "model_task_capture_gpu_gates_closed": not any((
            gates["model_loading_authorized"], gates["task_execution_authorized"],
            gates["real_branch_capture_authorized"], gates["model_runner_authorized"], gates["gpu_authorized"],
        )),
    }
    passed = all(checks.values())
    validation_inputs = (
        "configs/proper_v2_3/acquisition_runtime_protocol_v2_3.json",
        "configs/proper_v2_3/tau3_acquisition_action_effects_v2_3.json",
        "src/failure_memory/proper_v2/v2_3/acquisition_runtime_protocol.py",
        "experiments/proper_v2_3/scripted_acquisition_runtime_protocol_v2_3.py",
        "tests/test_proper_v2_3_acquisition_runtime_protocol.py",
        "schemas/proper_v2_3/acquisition_runtime_protocol_validation.schema.json",
    )
    result = {
        "schema_version": 1,
        "run_kind": "proper_v2_3_acquisition_runtime_protocol_validation",
        "protocol_sha256": _sha256(CONFIG),
        "action_registry_sha256": _sha256(REGISTRY),
        "task_hash_manifest_sha256": _canonical_sha256(config["task_hashes"]),
        "scripted_trace_sha256": trace_sha256,
        "validation_input_sha256": {path: _sha256(ROOT / path) for path in validation_inputs},
        "checks": checks,
        "passed": passed,
        "scoped_tests_run": 12,
        "public_tool_count": public_tool_count,
        "task_count": len(config["task_hashes"]),
        "model_loaded": False,
        "model_outputs_read": False,
        "task_executed": False,
        "gpu_used": False,
        "runtime_implementation_authorized": passed,
        "acquisition_runtime_freeze_authorized": False,
        "real_branch_capture_authorized": False,
        "model_runner_authorized": False,
        "confirmatory_run_authorized": False,
        "next_gate": "implement_acquisition_runtime_and_cpu_dry_run" if passed else "stop_runtime_protocol_design",
    }
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    checks["validation_envelope_matches_closed_schema_fields"] = set(result) == set(schema["required"])
    result["passed"] = all(checks.values())
    result["runtime_implementation_authorized"] = result["passed"]
    result["next_gate"] = "implement_acquisition_runtime_and_cpu_dry_run" if result["passed"] else "stop_runtime_protocol_design"
    return result, traces


def main() -> int:
    result, traces = validate()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "scripted_traces.json").write_bytes((json.dumps(traces, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    (OUTPUT_DIR / "validation.json").write_bytes((json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
