from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
CONFIG = (
    ROOT
    / "configs"
    / "proper_v2"
    / "toolsandbox_continuation_development_v2_2_1.yaml"
)
sys.path.insert(0, str(ROOT / "experiments" / "proper_v2"))

import continuation_development_v2_2_1 as continuation  # noqa: E402
import toolsandbox_model_pilot_runner_validation_v2_1 as engine  # noqa: E402
from failure_memory.proper_v2.v2_2 import (  # noqa: E402
    LifecycleObservation,
    LifecycleStatus,
    advance_lifecycle,
)
from failure_memory.proper_v2.v2_2_1 import (  # noqa: E402
    ReviewDisposition,
    review_decision,
)


class ScriptedContinuationProvider:
    """Scenario-blind apply/consume/repeat-block/replan-handoff provider."""

    def __init__(self, config: Mapping[str, Any]) -> None:
        self.lifecycle_policy = continuation.lifecycle_policy(config)
        self.continuation_policy = continuation.continuation_policy(config)

    def decide(
        self,
        *,
        record: Mapping[str, Any],
        condition: str,
        branch_history: list[dict[str, Any]],
        prefix_history: list[dict[str, Any]],
        decision_index: int,
        decisions_left: int,
        tool_calls_left: int,
    ) -> dict[str, Any]:
        del prefix_history, decision_index, decisions_left, tool_calls_left
        if condition in {"tfidf_rank1_memory", "proper_v2_1_memory"}:
            return {
                "kind": "stop",
                "reason_code": "persistent_condition_not_scripted",
                "message": "",
            }

        memory, lifecycle_state, state = (
            continuation.continuation_state_from_history(
                record,
                branch_history,
                lifecycle_runtime_policy=self.lifecycle_policy,
                continuation_runtime_policy=self.continuation_policy,
            )
        )
        if memory.proposed_action is None:
            stopped = advance_lifecycle(
                lifecycle_state,
                memory,
                LifecycleObservation(
                    phase=lifecycle_state.phase,
                    agent_stop_reason="scripted_safe_stop",
                ),
                self.lifecycle_policy,
            )
            return {
                "kind": "stop",
                "reason_code": "scripted_safe_stop",
                "message": "Required information is unavailable.",
                "_lifecycle": stopped.to_mapping(),
                "_continuation": state.to_mapping(),
            }
        if lifecycle_state.status == LifecycleStatus.ACTIVE:
            return {
                "kind": "tool",
                "tool_name": memory.proposed_action.tool_name,
                "arguments": dict(memory.proposed_action.argument_template),
                "_lifecycle": lifecycle_state.to_mapping(),
                "_continuation": state.to_mapping(),
            }
        if condition == "proper_lifecycle_prompt_only":
            return {
                "kind": "stop",
                "reason_code": "scripted_prompt_only_handoff",
                "message": "",
                "_lifecycle": lifecycle_state.to_mapping(),
                "_continuation": state.to_mapping(),
            }

        repeat = {
            "kind": "tool",
            "tool_name": memory.proposed_action.tool_name,
            "arguments": dict(memory.proposed_action.argument_template),
        }
        blocked = review_decision(
            state,
            lifecycle_state,
            memory,
            repeat,
            self.continuation_policy,
        )
        handoff = review_decision(
            blocked.state,
            lifecycle_state,
            memory,
            {
                "kind": "stop",
                "reason_code": "scripted_replan_handoff",
                "message": "",
            },
            self.continuation_policy,
        )
        return {
            "kind": "stop",
            "reason_code": "scripted_replan_handoff",
            "message": "",
            "_lifecycle": lifecycle_state.to_mapping(),
            "_continuation": handoff.state.to_mapping(),
            "_controller": {
                "blocked_repeat": repeat,
                "blocked_review": blocked.to_mapping(),
                "handoff_review": handoff.to_mapping(),
            },
        }


def dynamic_validation(config_path: Path = CONFIG) -> dict[str, Any]:
    config = continuation.load_config(config_path)
    provider = ScriptedContinuationProvider(config)
    raw = engine.run_validation(
        ROOT / str(config["frozen_inputs"]["runner_config"]["path"]),
        decision_provider=provider,
    )
    records = []
    condition_name = "proper_lifecycle_replan_controller"
    for record in raw["records"]:
        condition = record["conditions"][condition_name]
        decisions = condition["decisions"]
        controller_events = [
            item["_controller"]
            for item in decisions
            if "_controller" in item
        ]
        blocked_replans = [
            event
            for event in controller_events
            if event["blocked_review"]["disposition"] == "replan"
            and not event["blocked_review"]["decision_allowed"]
        ]
        records.append(
            {
                "pair_id": record["pair_id"],
                "decision_phase": record["decision_phase"],
                "identical_condition_start": record[
                    "identical_condition_start"
                ],
                "decision_count": condition["recovery_decision_count"],
                "tool_call_count": condition["recovery_tool_call_count"],
                "tool_exception_count": condition["tool_exception_count"],
                "executed_repeat_count": condition[
                    "repeated_identical_tool_call_count"
                ],
                "blocked_repeat_replan_count": len(blocked_replans),
                "replan_handoff": any(
                    event["handoff_review"]["disposition"] == "allow"
                    and event["handoff_review"]["decision_allowed"]
                    for event in controller_events
                ),
                "decisions": decisions,
                "raw_toolsandbox_evaluation": condition["evaluation"],
            }
        )
    post = [item for item in records if item["decision_phase"] == "post_failure"]
    pre = [item for item in records if item["decision_phase"] == "pre_action"]
    summary = {
        "pair_count": len(records),
        "condition_count": sum(
            len(item["conditions"]) for item in raw["records"]
        ),
        "identical_four_condition_start_count": sum(
            item["identical_condition_start"] for item in records
        ),
        "post_failure_pair_count": len(post),
        "pre_action_pair_count": len(pre),
        "post_failure_prerequisite_call_count": sum(
            item["tool_call_count"] for item in post
        ),
        "post_failure_blocked_repeat_replan_count": sum(
            item["blocked_repeat_replan_count"] for item in post
        ),
        "post_failure_executed_repeat_count": sum(
            item["executed_repeat_count"] for item in post
        ),
        "post_failure_tool_exception_count": sum(
            item["tool_exception_count"] for item in post
        ),
        "post_failure_replan_handoff_count": sum(
            item["replan_handoff"] for item in post
        ),
        "pre_action_tool_call_count": sum(
            item["tool_call_count"] for item in pre
        ),
    }
    checks = {
        "pair_count": summary["pair_count"] == 12,
        "condition_count": summary["condition_count"] == 48,
        "all_four_condition_starts_identical": summary[
            "identical_four_condition_start_count"
        ]
        == 12,
        "one_prerequisite_call_per_post_failure_pair": summary[
            "post_failure_prerequisite_call_count"
        ]
        == 9,
        "one_repeat_replan_per_post_failure_pair": summary[
            "post_failure_blocked_repeat_replan_count"
        ]
        == 9,
        "no_executed_repeats": summary[
            "post_failure_executed_repeat_count"
        ]
        == 0,
        "no_post_failure_tool_exceptions": summary[
            "post_failure_tool_exception_count"
        ]
        == 0,
        "all_post_failure_replans_handoff": summary[
            "post_failure_replan_handoff_count"
        ]
        == 9,
        "pre_action_executes_no_tools": summary[
            "pre_action_tool_call_count"
        ]
        == 0,
    }
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_2_1_toolsandbox_scripted_continuation_development",
        "identities": {
            "config_sha256": continuation.sha256_file(config_path),
            "prepared_manifest_sha256": config["frozen_inputs"][
                "prepared_manifest"
            ]["sha256"],
        },
        "summary": summary,
        "checks": checks,
        "passed": all(checks.values()),
        "records": records,
        "boundary": dict(config["boundary"]),
        "interpretation_limits": {
            "scripted_decisions_are_not_model_behavior": True,
            "existing_pairs_are_development_only": True,
            "continuation_state_transition_tested": True,
            "final_task_completion_not_tested": True,
            "raw_toolsandbox_scores_not_rewritten": True,
        },
    }


def write_result(
    result: Mapping[str, Any],
    config: Mapping[str, Any],
) -> Path:
    output = ROOT / str(config["outputs"]["dynamic_validation"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run scripted ToolSandbox continuation validation."
    )
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()
    config = continuation.load_config(args.config)
    result = dynamic_validation(args.config)
    output = write_result(result, config)
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2, sort_keys=True))
    print(f"OUTPUT={output}")
    status = "PASS" if result["passed"] else "STOP"
    print(f"RESULT={status}_PROPER_V2_2_1_TOOLSANDBOX_CONTINUATION")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
