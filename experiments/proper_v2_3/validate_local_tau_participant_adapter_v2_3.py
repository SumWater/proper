"""CPU-only validation for local Qwen tau participant message contracts."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PROMPTS = ROOT / "configs/proper_v2_3/local_tau_participant_prompts_v2_3.json"
SCHEMA = ROOT / "schemas/proper_v2_3/acquisition_participant_decision.schema.json"
OUTPUT = ROOT / "outputs/proper_v2_3/local_tau_participant_adapter/validation.json"
INPUTS = (
    "configs/proper_v2_3/local_tau_participant_prompts_v2_3.json",
    "schemas/proper_v2_3/acquisition_participant_decision.schema.json",
    "src/failure_memory/proper_v2/v2_3/acquisition_participants.py",
    "tests/test_proper_v2_3_acquisition_participants.py",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate() -> dict[str, Any]:
    prompts = json.loads(PROMPTS.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    tests = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_proper_v2_3_acquisition_participants"],
        cwd=ROOT, capture_output=True, text=True,
    )
    source = (ROOT / "src/failure_memory/proper_v2/v2_3/acquisition_participants.py").read_text(encoding="utf-8")
    hashes = {relative: _sha256(ROOT / relative) for relative in INPUTS}
    checks = {
        "eight_cpu_contract_tests_pass": tests.returncode == 0,
        "participant_decision_schema_is_exclusive": len(schema["oneOf"]) == 2,
        "agent_worker_roles_match_existing_worker": prompts["message_encoding"]["agent_supported_worker_roles"] == ["system", "user", "assistant"],
        "deterministic_generation_contract_frozen": not prompts["generation_contract"]["do_sample"] and prompts["generation_contract"]["temperature"] == 0.0,
        "private_scenario_not_sent_to_agent": not prompts["boundary"]["scenario_sent_to_agent"],
        "strict_json_parsers_present": "json.loads(raw_text)" in source and "parse_agent_output" in source and "parse_user_output" in source,
        "evaluator_metadata_guard_present": "FORBIDDEN_AGENT_KEYS" in source,
        "all_stage_inputs_hashed": len(hashes) == len(INPUTS),
        "task_model_gpu_gates_closed": not any((prompts["boundary"]["model_loading_authorized"], prompts["boundary"]["task_execution_authorized"], prompts["boundary"]["gpu_authorized"])),
    }
    passed = all(checks.values())
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_3_local_tau_participant_adapter_validation",
        "checks": checks,
        "passed": passed,
        "stage_input_sha256": hashes,
        "scoped_tests_run": 8,
        "model_loaded": False,
        "model_outputs_read": False,
        "task_executed": False,
        "gpu_used": False,
        "remote_model_inventory_authorized": passed,
        "acquisition_runtime_freeze_authorized": False,
        "real_branch_capture_authorized": False,
        "model_runner_authorized": False,
        "confirmatory_run_authorized": False,
        "next_gate": "run_remote_read_only_qwen_model_inventory",
    }


def main() -> int:
    result = validate()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
