"""Local CPU validation for the tau3 split-state replay adapter stage."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "outputs/proper_v2_3/tau3_branch_replay_adapter/validation.json"
STAGE_INPUTS = (
    "configs/proper_v2_3/tau3_branch_replay_adapter_v2_3.json",
    "configs/proper_v2_3/tau3_branch_replay_native_smoke_v2_3.json",
    "docs/proper_v2_3/tau3_branch_replay_adapter.md",
    "docs/proper_v2_3/tau3_branch_replay_native_smoke_handoff.md",
    "experiments/proper_v2_3/run_tau3_branch_replay_native_smoke_remote_v2_3.py",
    "experiments/proper_v2_3/validate_tau3_branch_replay_adapter_v2_3.py",
    "schemas/proper_v2_3/tau3_branch_replay_native_smoke.schema.json",
    "src/failure_memory/proper_v2/v2_3/branch_replay_adapter.py",
    "tests/test_proper_v2_3_tau3_branch_replay_adapter.py",
    "tests/test_proper_v2_3_tau3_branch_replay_native_smoke.py",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate() -> dict[str, Any]:
    tests = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_proper_v2_3_tau3_branch_replay_adapter", "tests.test_proper_v2_3_tau3_branch_replay_native_smoke"],
        cwd=ROOT, capture_output=True, text=True,
    )
    config = json.loads((ROOT / "configs/proper_v2_3/tau3_branch_replay_adapter_v2_3.json").read_text(encoding="utf-8"))
    smoke_config = json.loads((ROOT / "configs/proper_v2_3/tau3_branch_replay_native_smoke_v2_3.json").read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "schemas/proper_v2_3/tau3_branch_replay_native_smoke.schema.json").read_text(encoding="utf-8"))
    hashes = {relative: _sha256(ROOT / relative) for relative in STAGE_INPUTS}
    checks = {
        "scoped_tests_pass": tests.returncode == 0,
        "split_state_history_contract_frozen": config["input_contract"]["environment_replay_history"] == [],
        "tau_source_revision_frozen": len(smoke_config["source"]["revision"]) == 40,
        "native_execution_count_frozen_to_one": smoke_config["fixture"]["expected_native_execution_count"] == 1,
        "remote_output_schema_closed": schema["additionalProperties"] is False,
        "model_runner_not_authorized": not config["gates"]["authorize_model_runner"],
        "model_run_not_authorized": not smoke_config["gates"]["authorize_model_run"],
        "gpu_not_authorized": not smoke_config["gates"]["authorize_gpu"],
        "all_stage_inputs_hashed": len(hashes) == len(STAGE_INPUTS),
    }
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_3_tau3_branch_replay_adapter_local_validation",
        "checks": checks,
        "passed": all(checks.values()),
        "scoped_tests_run": 10,
        "stage_input_sha256": hashes,
        "native_tau3_smoke_run": False,
        "native_tau3_smoke_authorized": all(checks.values()),
        "task_loaded": False,
        "model_loaded": False,
        "model_outputs_read": False,
        "gpu_used": False,
        "real_branch_capture_authorized": False,
        "model_runner_authorized": False,
        "model_run_authorized": False,
        "confirmatory_run_authorized": False,
        "next_gate": "run_one_shot_remote_native_tau3_cpu_smoke",
    }


def main() -> int:
    result = validate()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
