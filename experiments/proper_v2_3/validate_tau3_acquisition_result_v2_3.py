"""Freeze and audit the stopped one-shot tau3 acquisition result."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/proper_v2_3/tau3_acquisition_result_freeze_v2_3.json"
FREEZE_SCHEMA = ROOT / "schemas/proper_v2_3/tau3_acquisition_result_freeze.schema.json"
RUN_SCHEMA = ROOT / "schemas/proper_v2_3/real_public_branch_capture_run_v2.schema.json"
OUTPUT = ROOT / "outputs/proper_v2_3/tau3_acquisition_result_freeze/validation.json"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate() -> dict[str, Any]:
    config = load(CONFIG)
    freeze_schema = load(FREEZE_SCHEMA)
    run_schema = load(RUN_SCHEMA)
    run_dir = ROOT / config["run"]["directory"]
    preflight = load(run_dir / "preflight.json")
    result = load(run_dir / "result.json")
    attempts = [load(run_dir / item["path"]) for item in result["attempt_artifacts"]]
    records = [
        record
        for attempt in attempts
        for record in attempt["worker_records"]
        if "usage" in record
    ]
    audited = {
        "model_request_count": len(records),
        "prompt_tokens": sum(item["usage"]["prompt_token_count"] for item in records),
        "completion_tokens": sum(item["usage"]["completion_token_count"] for item in records),
    }
    cost = result["cost"]
    reported = {
        "model_request_count": cost["agent_request_count"] + cost["user_request_count"],
        "prompt_tokens": cost["agent_prompt_tokens"] + cost["user_prompt_tokens"],
        "completion_tokens": cost["agent_completion_tokens"] + cost["user_completion_tokens"],
    }
    target_state_changes = sum(
        1
        for attempt in attempts
        for entry in attempt["public_state"]["ledger"]
        if entry["executed"] and entry["tool_name"] == attempt["target_tool_name"]
    )
    tests = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_proper_v2_3_tau3_acquisition_result_freeze"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    artifacts_match = all(
        (run_dir / item["path"]).stat().st_size == item["bytes"]
        and sha256(run_dir / item["path"]) == item["sha256"]
        for item in config["run"]["artifacts"]
    )
    checks = {
        "all_returned_artifacts_match_bytes_and_hashes": artifacts_match,
        "all_frozen_inputs_match_hashes": all(
            sha256(ROOT / item["path"]) == item["sha256"] for item in config["frozen_inputs"]
        ),
        "preflight_passed_all_checks": preflight["passed"] and all(preflight["checks"].values()),
        "returned_result_matches_closed_run_shape": (
            set(result) == set(run_schema["properties"])
            and set(result) == set(run_schema["required"])
            and result["schema_version"] == 2
        ),
        "stopped_at_fifth_attempt_with_four_pre_action_captures": (
            result["status"] == "capture_stopped"
            and result["stop_reason"] == "invalid_user_output"
            and len(attempts) == 5
            and [item["public_state"]["status"] for item in attempts] == ["captured"] * 4 + ["capture_failure"]
            and result["captured_branch_count"] == 4
            and result["post_failure_captured_count"] == 0
        ),
        "invalid_user_output_preserved_without_retry": (
            attempts[-1]["public_state"]["failure_reason"] == "invalid_user_output"
            and "parse_error" in attempts[-1]["worker_records"][-1]
            and not any(
                record["request_id"].startswith("attempt-06")
                for attempt in attempts
                for record in attempt["worker_records"]
            )
        ),
        "no_target_or_non_idempotent_side_effect_executed": (
            target_state_changes == 0
            and result["duplicate_non_idempotent_execution_count"] == 0
            and not any(
                entry["executed"] and entry["effect_class"] == "non_idempotent_side_effect"
                for attempt in attempts
                for entry in attempt["public_state"]["ledger"]
            )
        ),
        "reported_cost_matches_returned_result": reported == config["cost_audit"]["reported"],
        "worker_record_cost_recomputed": audited == config["cost_audit"]["worker_record_recomputed"],
        "invalid_output_cost_undercount_detected": (
            {key: audited[key] - reported[key] for key in audited}
            == config["cost_audit"]["omitted_invalid_user_response"]
            and not config["cost_audit"]["reported_cost_complete"]
        ),
        "model_task_and_gpu_boundaries_reported_open": all(
            result["boundary"][key]
            for key in ("model_loaded", "model_outputs_read", "task_executed", "gpu_used")
        ),
        "six_freeze_tests_pass": tests.returncode == 0 and "Ran 6 tests" in tests.stderr,
        "rerun_comparison_and_claim_gates_closed": (
            not config["disposition"]["rerun_or_resume_authorized"]
            and not config["disposition"]["comparison_runner_authorized"]
            and not config["disposition"]["confirmatory_claim_authorized"]
        ),
        "freeze_schema_is_closed": freeze_schema["additionalProperties"] is False,
    }
    value: dict[str, Any] = {
        "schema_version": 1,
        "run_kind": "proper_v2_3_tau3_acquisition_result_freeze",
        "passed": False,
        "checks": checks,
        "freeze_config_sha256": sha256(CONFIG),
        "result_sha256": sha256(run_dir / "result.json"),
        "preflight_sha256": sha256(run_dir / "preflight.json"),
        "worker_stderr_sha256": sha256(run_dir / "worker.stderr"),
        "remote_project_revision": result["project_revision"],
        "capture_attempt_count": result["capture_attempt_count"],
        "captured_branch_count": result["captured_branch_count"],
        "post_failure_captured_count": result["post_failure_captured_count"],
        "stop_reason": result["stop_reason"],
        "reported_model_request_count": reported["model_request_count"],
        "audited_model_request_count": audited["model_request_count"],
        "reported_prompt_tokens": reported["prompt_tokens"],
        "audited_prompt_tokens": audited["prompt_tokens"],
        "reported_completion_tokens": reported["completion_tokens"],
        "audited_completion_tokens": audited["completion_tokens"],
        "cost_accounting_complete": False,
        "duplicate_non_idempotent_execution_count": result["duplicate_non_idempotent_execution_count"],
        "target_state_change_execution_count": target_state_changes,
        "model_loaded": result["boundary"]["model_loaded"],
        "model_outputs_read": result["boundary"]["model_outputs_read"],
        "task_executed": result["boundary"]["task_executed"],
        "gpu_used": result["boundary"]["gpu_used"],
        "scientific_stage_passed": False,
        "rerun_authorized": False,
        "comparison_protocol_authorized": False,
        "confirmatory_claim_authorized": False,
        "next_gate": "stop_tau3_acquisition_line_and_report",
    }
    checks["validation_matches_closed_schema_fields"] = (
        set(value) == set(freeze_schema["required"])
        and set(value) <= set(freeze_schema["properties"])
    )
    value["passed"] = all(checks.values())
    return value


def main() -> int:
    result = validate()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
