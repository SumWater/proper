"""CPU-only validation of the one-shot remote acquisition runner."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/proper_v2_3/acquisition_one_shot_runner_implementation_v2_3.json"
RUNNER = ROOT / "experiments/proper_v2_3/run_tau3_acquisition_remote_v2_3.py"
RUN_SCHEMA = ROOT / "schemas/proper_v2_3/real_public_branch_capture_run_v2.schema.json"
VALIDATION_SCHEMA = ROOT / "schemas/proper_v2_3/acquisition_one_shot_runner_implementation_validation.schema.json"
OUTPUT = ROOT / "outputs/proper_v2_3/acquisition_one_shot_runner_implementation/validation.json"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def top_level_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def main() -> int:
    config = load(CONFIG)
    schema = load(RUN_SCHEMA)
    validation_schema = load(VALIDATION_SCHEMA)
    tests = subprocess.run(
        [sys.executable,"-m","unittest",
         "tests.test_proper_v2_3_acquisition_one_shot_runner",
         "tests.test_proper_v2_3_acquisition_one_shot_runner_protocol",
         "tests.test_proper_v2_3_acquisition_runtime"],
        cwd=ROOT,capture_output=True,text=True,check=False,
    )
    hashes_match = all(sha256(ROOT / item["path"]) == item["sha256"] for item in config["implementation_inputs"])
    correction = config["pre_model_schema_correction"]
    attempt_fields = schema["properties"]["attempt_artifacts"]["items"]["properties"]
    runner_source = RUNNER.read_text(encoding="utf-8")
    gates = config["gates"]
    checks = {
        "all_declared_implementation_hashes_match": hashes_match,
        "frozen_protocol_and_validation_hashes_match": sha256(ROOT / config["protocol"]["path"]) == config["protocol"]["sha256"] and sha256(ROOT / config["protocol"]["validation_path"]) == config["protocol"]["validation_sha256"],
        "frozen_v1_run_schema_unchanged": not correction["modify_v1"] and sha256(ROOT / correction["frozen_v1_path"]) == correction["frozen_v1_sha256"],
        "v2_schema_separates_trajectory_and_target_counts": "maximum" not in attempt_fields["native_tool_execution_count"] and attempt_fields["target_native_execution_count"]["maximum"] == 1,
        "twenty_four_scoped_tests_pass": tests.returncode == 0 and "Ran 24 tests" in tests.stderr,
        "runner_has_no_top_level_tau_or_model_import": not (top_level_imports(RUNNER) & {"tau2","torch","transformers","accelerate"}),
        "runner_requires_exact_revision_argument": 'parser.add_argument("--expected-project-revision", required=True)' in runner_source,
        "runner_has_no_synthetic_cli_escape_hatch": "--cpu-dry-run" not in runner_source and "--synthetic" not in runner_source,
        "preflight_checks_model_inventory_tau_inputs_python_and_cuda": all(token in runner_source for token in ("inventory_regular_files","execution_manifest","load_and_verify_tasks","worker_dependencies_available","cuda_device_zero_available")),
        "full_and_partial_synthetic_orchestration_are_tested": config["cpu_validation"]["full_synthetic_pair_count"] == 12 and config["cpu_validation"]["early_stop_fixture_ordinal"] == 5,
        "atomic_attempt_and_progress_persistence_present": "atomic_json(path, attempt)" in runner_source and "progress_callback" in runner_source,
        "retry_resume_and_replacement_remain_forbidden": config["protocol"]["sha256"] == "ad5fb6a719969aa1dde6a9ba4d88d3d5683eb543f11ebee3fc81d7104e5d5668",
        "remote_authority_is_conditional_on_this_validation": gates["cpu_validation_required_before_remote_command"] and gates["remote_command_authorized_after_validation"],
        "comparison_and_confirmatory_gates_remain_closed": not gates["comparison_runner_authorized"] and not gates["confirmatory_claim_authorized"],
        "validation_output_schema_is_closed": validation_schema["additionalProperties"] is False,
    }
    passed = all(checks.values())
    inputs = [CONFIG,RUNNER,RUN_SCHEMA,VALIDATION_SCHEMA,ROOT / "tests/test_proper_v2_3_acquisition_one_shot_runner.py",ROOT / "tests/test_proper_v2_3_acquisition_one_shot_runner_protocol.py"]
    result: dict[str, Any] = {
        "schema_version":1,"run_kind":"proper_v2_3_acquisition_one_shot_runner_implementation_validation","passed":passed,"checks":checks,
        "implementation_config_sha256":sha256(CONFIG),"input_sha256":{path.relative_to(ROOT).as_posix():sha256(path) for path in inputs},
        "scoped_tests_run":24,"runner_implemented":True,"remote_command_authorized":passed,
        "model_loaded":False,"model_outputs_read":False,"task_executed":False,"gpu_used":False,
        "next_gate":"run_one_shot_remote_tau3_acquisition" if passed else "stop_runner_implementation",
    }
    required, allowed = set(validation_schema["required"]), set(validation_schema["properties"])
    result["checks"]["validation_output_matches_closed_schema_fields"] = required <= set(result) <= allowed
    result["passed"] = all(result["checks"].values())
    result["remote_command_authorized"] = result["passed"]
    result["next_gate"] = "run_one_shot_remote_tau3_acquisition" if result["passed"] else "stop_runner_implementation"
    atomic_json(OUTPUT,result)
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
