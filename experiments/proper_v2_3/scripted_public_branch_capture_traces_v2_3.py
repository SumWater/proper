"""CPU-only scripted traces for public branch capture and replay separation."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
CONFIG = ROOT / "configs/proper_v2_3/public_branch_capture_design_v2_3.json"
OUTPUT = ROOT / "outputs/proper_v2_3/public_branch_capture_design/scripted_traces.json"

from src.failure_memory.proper_v2.v2_3.branch_capture import (
    PublicBranchCapture,
    assert_identical_starts,
)


def _call(call_id: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {"role": "assistant", "tool_calls": [{"id": call_id, "name": name, "arguments": arguments}]}


def _receipt(call_id: str, content: Any, *, error: bool, outcome: str) -> dict[str, Any]:
    return {"role": "tool", "tool_call_id": call_id, "content": content, "error": error, "outcome": outcome}


def _captures() -> list[tuple[str, PublicBranchCapture]]:
    opening = {"role": "user", "content": "Please complete the requested account task."}
    return [
        (
            "read_only_pre_action",
            PublicBranchCapture(
                public_history=(opening,), effect_class="read_only",
                receipt_kind="pre_action_trigger", guarded_call_id=None,
                native_execution_observed=False,
                checkpoint_payload={"records": {"account": {"status": "open"}}},
                checkpoint_applied_call_ids=(),
                controller_state={"ledger": [], "memory_state": "active"},
            ),
        ),
        (
            "idempotent_failed_without_execution",
            PublicBranchCapture(
                public_history=(opening, _call("call-setting", "set_account_flag", {"value": True}),
                    _receipt("call-setting", {"code": "reference_not_found"}, error=True, outcome="failed")),
                effect_class="idempotent_state_setting", receipt_kind="executed_failure",
                guarded_call_id="call-setting", native_execution_observed=False,
                checkpoint_payload={"records": {"account": {"flag": False}}},
                checkpoint_applied_call_ids=(),
                controller_state={"ledger": [{"call_id": "call-setting", "outcome": "failed"}], "memory_state": "active"},
            ),
        ),
        (
            "non_idempotent_executed_unknown",
            PublicBranchCapture(
                public_history=(opening, _call("call-side-effect", "send_notification", {"body": "status"}),
                    _receipt("call-side-effect", {"code": "result_unknown"}, error=True, outcome="unknown")),
                effect_class="non_idempotent_side_effect", receipt_kind="outcome_unknown",
                guarded_call_id="call-side-effect", native_execution_observed=True,
                checkpoint_payload={"records": {"notifications": [{"body": "status"}]}},
                checkpoint_applied_call_ids=("call-side-effect",),
                controller_state={"ledger": [{"call_id": "call-side-effect", "outcome": "unknown"}], "memory_state": "active"},
            ),
        ),
    ]


def run_traces() -> dict[str, Any]:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    traces = []
    for trace_id, capture in _captures():
        view = capture.method_view()
        plan = capture.replay_plan()
        starts = assert_identical_starts(capture, config["conditions"])
        checks = {
            "five_conditions_share_start": len(set(starts.values())) == 1 and len(starts) == 5,
            "participant_history_complete": plan["participant_message_history"] == view["public_history"],
            "environment_replay_history_empty": plan["environment_replay_history"] == [],
            "checkpoint_not_in_method_view": "environment_checkpoint" not in view,
            "checkpoint_hash_present": len(plan["checkpoint_sha256"]) == 64,
            "executed_unknown_is_not_replayed": (
                capture.receipt_kind != "outcome_unknown"
                or capture.guarded_call_id in plan["skip_environment_replay_call_ids"]
            ),
        }
        traces.append({
            "trace_id": trace_id,
            "effect_class": capture.effect_class,
            "receipt_kind": capture.receipt_kind,
            "native_execution_observed": capture.native_execution_observed,
            "identical_start_sha256": plan["identical_start_sha256"],
            "condition_start_sha256": starts,
            "checks": checks,
            "passed": all(checks.values()),
        })
    checks = {
        "all_traces_pass": all(item["passed"] for item in traces),
        "three_effect_class_traces": len({item["effect_class"] for item in traces}) == 3,
        "unknown_outcome_trace_present": any(item["receipt_kind"] == "outcome_unknown" for item in traces),
    }
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_3_scripted_public_branch_capture_traces",
        "checks": checks,
        "passed": all(checks.values()),
        "trace_count": len(traces),
        "traces": traces,
        "task_executed": False,
        "model_loaded": False,
        "model_outputs_read": False,
        "gpu_used": False,
        "tau3_runtime_adapter_authorized": all(checks.values()),
        "model_runner_authorized": False,
        "model_run_authorized": False,
        "confirmatory_run_authorized": False,
        "next_gate": "implement_cpu_only_tau3_branch_replay_adapter",
    }


def main() -> int:
    result = run_traces()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "trace_count": result["trace_count"]}, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
