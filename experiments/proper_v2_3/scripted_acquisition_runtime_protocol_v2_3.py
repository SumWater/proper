"""Dependency-free traces for the acquisition-runtime protocol state machine."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.failure_memory.proper_v2.v2_3.acquisition_runtime_protocol import AcquisitionProtocolMachine

USAGE = {"prompt_token_count": 12, "completion_token_count": 3}
REGISTRY = {
    "read": "read_only", "set": "idempotent_state_setting", "send": "non_idempotent_side_effect"
}


def run_traces() -> dict[str, Any]:
    pre = AcquisitionProtocolMachine("pre_action", "read", "read_only", REGISTRY)
    pre.record_user_message("start", USAGE)

    setting = AcquisitionProtocolMachine("post_failure", "set", "idempotent_state_setting", REGISTRY)
    setting.record_user_message("start", USAGE)
    setting.record_agent_decision(
        {"kind":"tool","tool_name":"set","arguments":{"value":1}}, USAGE,
        pre_action_checkpoint_sha256="1" * 64,
    )

    side_effect = AcquisitionProtocolMachine("post_failure", "send", "non_idempotent_side_effect", REGISTRY)
    side_effect.record_user_message("start", USAGE)
    side_effect.record_agent_decision({"kind":"tool","tool_name":"send","arguments":{"value":1}}, USAGE)
    side_effect.record_environment_result(
        content={"secret_native_result":True}, error=False, outcome="succeeded", native_executed=True,
        post_action_checkpoint_sha256="2" * 64,
    )

    duplicate = AcquisitionProtocolMachine("post_failure", "send", "non_idempotent_side_effect", REGISTRY)
    duplicate.record_user_message("start", USAGE)
    repeated = {"kind":"tool","tool_name":"set","arguments":{"value":1}}
    duplicate.record_agent_decision(repeated, USAGE)
    duplicate.record_environment_result(content={"ok":True}, error=False, outcome="succeeded", native_executed=True)
    duplicate.record_agent_decision(repeated, USAGE)

    invalid = AcquisitionProtocolMachine("post_failure", "set", "idempotent_state_setting", REGISTRY)
    invalid.record_user_message("start", USAGE)
    invalid.record_invalid_output("agent")

    worker = AcquisitionProtocolMachine("pre_action", "read", "read_only", REGISTRY)
    worker.record_worker_error("user")

    traces = {
        "pre_action": pre.public_snapshot(),
        "idempotent_target": setting.public_snapshot(),
        "non_idempotent_target": side_effect.public_snapshot(),
        "duplicate_state_change": duplicate.public_snapshot(),
        "invalid_output": invalid.public_snapshot(),
        "worker_error": worker.public_snapshot(),
    }
    checks = {
        "pre_action_captured_before_agent": pre.status == "captured" and pre.agent_usage.requests == 0,
        "idempotent_target_suppressed": setting.status == "captured" and setting.target_native_execution_count == 0,
        "non_idempotent_target_executed_once": side_effect.status == "captured" and side_effect.target_native_execution_count == 1,
        "native_result_hidden": "secret_native_result" not in json.dumps(side_effect.public_history),
        "duplicate_state_change_blocked": duplicate.status == "safety_failure" and duplicate.native_tool_execution_count == 1,
        "invalid_output_not_retried": invalid.failure_reason == "invalid_agent_output",
        "worker_error_preserved": worker.status == "infrastructure_failure",
        "evaluator_routing_absent_from_public_snapshots": all(
            "target_tool_name" not in trace and "phase" not in trace for trace in traces.values()
        ),
    }
    return {"schema_version":1,"run_kind":"proper_v2_3_scripted_acquisition_runtime_protocol","checks":checks,"passed":all(checks.values()),"traces":traces,"model_loaded":False,"task_executed":False,"gpu_used":False}


if __name__ == "__main__":
    print(json.dumps(run_traces(), ensure_ascii=False, indent=2, sort_keys=True))
