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
    / "toolsandbox_lifecycle_development_v2_2.yaml"
)
sys.path.insert(0, str(ROOT / "experiments" / "proper_v2"))

import lifecycle_development_v2_2 as lifecycle  # noqa: E402
import toolsandbox_model_pilot_runner_validation_v2_1 as engine  # noqa: E402


class ScriptedLifecycleProvider:
    """A scenario-blind provider that tests apply/consume/handoff only."""

    def __init__(self, config: Mapping[str, Any]) -> None:
        self.policy = lifecycle.lifecycle_policy(config)

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
        if condition != "proper_v2_1_memory":
            return {
                "kind": "stop",
                "reason_code": "non_lifecycle_condition_not_evaluated",
                "message": "",
            }
        memory, state = lifecycle.state_from_history(
            record,
            branch_history,
            self.policy,
        )
        if state.status == lifecycle.LifecycleStatus.CONSUMED:
            return {
                "kind": "stop",
                "reason_code": "ordinary_planning_handoff",
                "message": "",
                "_lifecycle": state.to_mapping(),
            }
        if state.status != lifecycle.LifecycleStatus.ACTIVE:
            return {
                "kind": "stop",
                "reason_code": f"lifecycle_{state.status.value}",
                "message": "",
                "_lifecycle": state.to_mapping(),
            }
        if memory.proposed_action is None:
            stopped = lifecycle.advance_lifecycle(
                state,
                memory,
                lifecycle.LifecycleObservation(
                    phase=state.phase,
                    agent_stop_reason="scripted_safe_stop",
                ),
                self.policy,
            )
            return {
                "kind": "stop",
                "reason_code": "scripted_safe_stop",
                "message": "Required information is unavailable.",
                "_lifecycle": stopped.to_mapping(),
            }
        return {
            "kind": "tool",
            "tool_name": memory.proposed_action.tool_name,
            "arguments": dict(memory.proposed_action.argument_template),
            "_lifecycle": state.to_mapping(),
        }


def dynamic_validation(config_path: Path = CONFIG) -> dict[str, Any]:
    config = lifecycle.load_config(config_path)
    provider = ScriptedLifecycleProvider(config)
    raw = engine.run_validation(
        ROOT
        / str(config["frozen_inputs"]["v2_1_runner_config"]["path"]),
        decision_provider=provider,
    )
    records = []
    for record in raw["records"]:
        condition = record["conditions"]["proper_v2_1_memory"]
        decisions = condition["decisions"]
        lifecycle_states = [
            item["_lifecycle"]
            for item in decisions
            if "_lifecycle" in item
        ]
        final = lifecycle_states[-1]
        records.append(
            {
                "pair_id": record["pair_id"],
                "decision_phase": record["decision_phase"],
                "final_lifecycle": final,
                "decision_count": condition["recovery_decision_count"],
                "tool_call_count": condition["recovery_tool_call_count"],
                "tool_exception_count": condition["tool_exception_count"],
                "repeated_identical_tool_call_count": condition[
                    "repeated_identical_tool_call_count"
                ],
                "ordinary_planning_handoff": any(
                    item.get("reason_code") == "ordinary_planning_handoff"
                    for item in decisions
                ),
                "raw_toolsandbox_evaluation": condition["evaluation"],
            }
        )
    post = [item for item in records if item["decision_phase"] == "post_failure"]
    pre = [item for item in records if item["decision_phase"] == "pre_action"]
    summary = {
        "pair_count": len(records),
        "post_failure_consumed_count": sum(
            item["final_lifecycle"]["status"] == "consumed" for item in post
        ),
        "pre_action_stopped_count": sum(
            item["final_lifecycle"]["status"] == "stopped" for item in pre
        ),
        "ordinary_planning_handoff_count": sum(
            item["ordinary_planning_handoff"] for item in post
        ),
        "post_failure_tool_exception_count": sum(
            item["tool_exception_count"] for item in post
        ),
        "memory_action_repeat_count": sum(
            item["repeated_identical_tool_call_count"] for item in post
        ),
        "post_failure_tool_call_count": sum(
            item["tool_call_count"] for item in post
        ),
    }
    expected = config["scripted_expectations"]
    checks = {
        "pair_count": summary["pair_count"]
        == int(config["development_cohort"]["pair_count"]),
        "post_failure_consumed": summary["post_failure_consumed_count"]
        == int(expected["post_failure_consumed_count"]),
        "pre_action_stopped": summary["pre_action_stopped_count"]
        == int(expected["pre_action_stopped_count"]),
        "ordinary_planning_handoff": summary[
            "ordinary_planning_handoff_count"
        ]
        == int(expected["ordinary_planning_handoff_count"]),
        "no_memory_action_repeats": summary["memory_action_repeat_count"]
        == int(expected["memory_action_repeat_count"]),
        "no_post_failure_tool_exceptions": summary[
            "post_failure_tool_exception_count"
        ]
        == int(expected["post_failure_tool_exception_count"]),
        "one_recovery_call_per_post_failure_pair": summary[
            "post_failure_tool_call_count"
        ]
        == len(post),
    }
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_2_toolsandbox_scripted_lifecycle_development",
        "identities": {
            "config_sha256": lifecycle.sha256_file(config_path),
            "prepared_manifest_sha256": config["frozen_inputs"][
                "v2_1_prepared_manifest"
            ]["sha256"],
        },
        "summary": summary,
        "checks": checks,
        "passed": all(checks.values()),
        "records": records,
        "boundary": dict(config["boundary"]),
        "interpretation_limits": {
            "scripted_decisions_are_not_model_behavior": True,
            "v2_1_pairs_are_development_only": True,
            "selector_first_step_not_retested": True,
            "lifecycle_transition_tested": True,
            "ordinary_planning_handoff_tested": True,
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
        description="Run the scenario-blind ToolSandbox lifecycle validation."
    )
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()
    config = lifecycle.load_config(args.config)
    result = dynamic_validation(args.config)
    output = write_result(result, config)
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2, sort_keys=True))
    print(f"OUTPUT={output}")
    status = "PASS" if result["passed"] else "STOP"
    print(f"RESULT={status}_PROPER_V2_2_TOOLSANDBOX_LIFECYCLE_VALIDATION")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
