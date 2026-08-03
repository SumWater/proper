"""CPU-only validation of the future one-shot acquisition-runner protocol."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/proper_v2_3/acquisition_one_shot_runner_protocol_v2_3.json"
RUN_SCHEMA = ROOT / "schemas/proper_v2_3/real_public_branch_capture_run.schema.json"
VALIDATION_SCHEMA = ROOT / "schemas/proper_v2_3/acquisition_one_shot_runner_protocol_validation.schema.json"
TEST = ROOT / "tests/test_proper_v2_3_acquisition_one_shot_runner_protocol.py"
OUTPUT = ROOT / "outputs/proper_v2_3/acquisition_one_shot_runner_protocol/validation.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def closed_shape(value: dict[str, Any], schema: dict[str, Any]) -> bool:
    required = set(schema["required"])
    allowed = set(schema["properties"])
    return required <= set(value) <= allowed


def main() -> int:
    config = load(CONFIG)
    run_schema = load(RUN_SCHEMA)
    validation_schema = load(VALIDATION_SCHEMA)
    test_result = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_proper_v2_3_acquisition_one_shot_runner_protocol"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    frozen_inputs_match = all(sha256(ROOT / item["path"]) == item["sha256"] for item in config["frozen_inputs"])
    execution = config["execution"]
    gates = config["gates"]
    checks = {
        "all_frozen_input_hashes_match": frozen_inputs_match,
        "six_scoped_protocol_tests_pass": test_result.returncode == 0 and "Ran 6 tests" in test_result.stderr,
        "smoke_is_first_and_counts_as_only_pair_attempt": execution["capture_order"][0] == execution["smoke_pair_id"] and execution["attempts_per_pair"] == 1 and execution["smoke_is_the_only_attempt_for_that_pair"],
        "all_twelve_pair_ids_are_unique_and_frozen": len(execution["capture_order"]) == len(set(execution["capture_order"])) == 12,
        "early_stop_output_accepts_partial_attempt_count": run_schema["properties"]["capture_attempt_count"]["minimum"] == 0 and run_schema["properties"]["capture_attempt_count"]["maximum"] == 12,
        "frozen_v1_schema_is_not_modified": config["schema_correction_before_model_output"]["modify_v1_schema"] is False,
        "retry_resume_resample_and_worker_restart_are_zero": not execution["resume_after_interruption"] and not execution["rerun_failed_or_interrupted_pair"] and not execution["replacement_or_resampling"] and config["model_worker"]["restart_count"] == 0,
        "one_native_non_idempotent_execution_is_the_limit": execution["native_non_idempotent_execution_limit_per_pair"] == 1,
        "external_network_and_api_are_closed": not config["remote_runtime"]["external_network_allowed"] and not config["remote_runtime"]["external_api_allowed"],
        "partial_failed_and_worker_stderr_evidence_are_preserved": config["persistence"]["partial_and_failed_runs_preserved"] and config["persistence"]["worker_stderr_preserved"],
        "runner_file_does_not_exist_at_design_freeze": not (ROOT / config["future_entrypoint_contract"]["runner_path"]).exists(),
        "model_task_capture_remote_gpu_gates_are_closed": all(not gates[key] for key in ("runner_implemented","remote_command_authorized","model_loading_authorized","task_execution_authorized","real_branch_capture_authorized","gpu_authorized","confirmatory_claim_authorized")),
    }
    passed = all(checks.values())
    input_paths = [CONFIG, RUN_SCHEMA, VALIDATION_SCHEMA, TEST]
    result: dict[str, Any] = {
        "schema_version": 1,
        "run_kind": "proper_v2_3_acquisition_one_shot_runner_protocol_validation",
        "passed": passed,
        "checks": checks,
        "protocol_config_sha256": sha256(CONFIG),
        "input_sha256": {str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path) for path in input_paths},
        "scoped_tests_run": 6,
        "runner_implemented": False,
        "model_loaded": False,
        "model_outputs_read": False,
        "task_executed": False,
        "gpu_used": False,
        "remote_command_authorized": False,
        "runner_implementation_authorized": passed,
        "next_gate": "implement_and_cpu_validate_one_shot_acquisition_runner" if passed else "stop_protocol_design",
    }
    result["checks"]["validation_output_matches_closed_schema_fields"] = closed_shape(result, validation_schema)
    result["passed"] = all(result["checks"].values())
    result["runner_implementation_authorized"] = result["passed"]
    result["next_gate"] = "implement_and_cpu_validate_one_shot_acquisition_runner" if result["passed"] else "stop_protocol_design"
    atomic_json(OUTPUT, result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
