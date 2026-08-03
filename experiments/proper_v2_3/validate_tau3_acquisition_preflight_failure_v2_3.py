"""Freeze the returned clean-worktree-only acquisition preflight failure."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/proper_v2_3/tau3_acquisition_preflight_failure_freeze_v2_3.json"
SCHEMA = ROOT / "schemas/proper_v2_3/tau3_acquisition_preflight_failure_freeze.schema.json"
RUN_SCHEMA = ROOT / "schemas/proper_v2_3/real_public_branch_capture_run_v2.schema.json"
OUTPUT = ROOT / "outputs/proper_v2_3/tau3_acquisition_preflight_failure_freeze/validation.json"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    config, schema, run_schema = load(CONFIG), load(SCHEMA), load(RUN_SCHEMA)
    run = config["failed_run"]
    preflight, result = load(ROOT / run["preflight_path"]), load(ROOT / run["result_path"])
    tests = subprocess.run([sys.executable,"-m","unittest","tests.test_proper_v2_3_tau3_acquisition_preflight_failure_freeze"],cwd=ROOT,capture_output=True,text=True,check=False)
    failed_checks = [key for key, value in preflight["checks"].items() if not value]
    boundary, cost = result["boundary"], result["cost"]
    checks = {
        "returned_preflight_hash_matches":sha256(ROOT / run["preflight_path"]) == run["preflight_sha256"],
        "returned_result_hash_matches":sha256(ROOT / run["result_path"]) == run["result_sha256"],
        "all_frozen_inputs_match":all(sha256(ROOT / item["path"]) == item["sha256"] for item in config["frozen_inputs"]),
        "only_tracked_worktree_clean_failed":failed_checks == ["tracked_worktree_clean"],
        "all_other_preflight_checks_passed":sum(preflight["checks"].values()) == 11,
        "zero_attempt_request_token_and_tool_counts":result["capture_attempt_count"] == 0 and not result["attempt_artifacts"] and all(cost[key] == 0 for key in ("agent_request_count","user_request_count","native_tool_execution_count","agent_prompt_tokens","user_prompt_tokens")),
        "model_task_output_and_gpu_boundaries_closed":not any((boundary["model_loaded"],boundary["model_outputs_read"],boundary["task_executed"],boundary["gpu_used"])),
        "four_freeze_tests_pass":tests.returncode == 0 and "Ran 4 tests" in tests.stderr,
        "retry_changes_no_scientific_input":not config["failure_classification"]["scientific_protocol_changed"] and not config["retry_gate"]["method_prompt_budget_model_task_order_or_endpoint_change_allowed"],
        "retry_requires_committed_clean_worktree_and_unique_output":config["retry_gate"]["require_reported_readmes_committed"] and config["retry_gate"]["require_clean_tracked_worktree"] and config["retry_gate"]["require_new_unique_output_directory"],
        "validation_schema_is_closed":schema["additionalProperties"] is False,
        "returned_result_matches_closed_run_shape":set(run_schema["required"]) <= set(result) <= set(run_schema["properties"]) and result["schema_version"] == 2,
    }
    passed = all(checks.values())
    value: dict[str, Any] = {"schema_version":1,"run_kind":"proper_v2_3_tau3_acquisition_preflight_failure_freeze","passed":passed,"checks":checks,"freeze_config_sha256":sha256(CONFIG),"preflight_sha256":sha256(ROOT / run["preflight_path"]),"result_sha256":sha256(ROOT / run["result_path"]),"failed_project_revision":run["project_revision"],"failed_preflight_preserved":True,"model_loaded":False,"model_outputs_read":False,"task_executed":False,"gpu_used":False,"infrastructure_retry_authorized":passed,"next_gate":"one_clean_worktree_acquisition_retry" if passed else "stop_and_preserve_preflight_failure"}
    required, allowed = set(schema["required"]), set(schema["properties"])
    value["checks"]["validation_matches_closed_schema_fields"] = required <= set(value) <= allowed
    value["passed"] = all(value["checks"].values())
    value["infrastructure_retry_authorized"] = value["passed"]
    value["next_gate"] = "one_clean_worktree_acquisition_retry" if value["passed"] else "stop_and_preserve_preflight_failure"
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_bytes((json.dumps(value,ensure_ascii=False,indent=2,sort_keys=True)+"\n").encode("utf-8"))
    print(json.dumps(value,ensure_ascii=False,sort_keys=True))
    return 0 if value["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
