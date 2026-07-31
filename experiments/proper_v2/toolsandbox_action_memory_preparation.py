from __future__ import annotations

import argparse
import copy
import hashlib
import json
import random
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
CONFIG = (
    ROOT
    / "configs"
    / "proper_v2"
    / "toolsandbox_action_memory_preparation.yaml"
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if (
        config.get("status")
        != "exploratory_scripted_source_trajectory_memory_preparation"
    ):
        raise RuntimeError("action-memory preparation config has invalid status")
    return config


def resolve_and_verify(value: Mapping[str, Any]) -> Path:
    path = ROOT / str(value["path"])
    if sha256_file(path) != str(value["sha256"]):
        raise RuntimeError(f"input hash mismatch: {path}")
    return path


def behavior_signature(action: Mapping[str, Any]) -> str:
    return json.dumps(
        {
            "recovery_operation": "invoke_prerequisite",
            "tool_name": str(action["tool"]),
            "arguments": dict(action["arguments"]),
            "continuation_policy": "verify_then_continue",
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def prepare(config_path: Path = CONFIG) -> dict[str, Any]:
    config = load_config(config_path)
    inventory_path = resolve_and_verify(config["inputs"]["dynamic_inventory"])
    smoke_path = resolve_and_verify(config["inputs"]["scripted_smoke"])
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    smoke = json.loads(smoke_path.read_text(encoding="utf-8"))
    if not inventory["dynamic_inventory_ready"] or not smoke["scripted_smoke_passed"]:
        raise RuntimeError("upstream ToolSandbox validation did not pass")

    repository = ROOT / "external" / "toolsandbox"
    sys.path.insert(0, str(repository))
    try:
        from tool_sandbox.common.execution_context import (  # type: ignore
            DatabaseNamespace,
            RoleType,
            get_current_context,
            set_current_context,
        )
        from tool_sandbox.common.message_conversion import Message  # type: ignore
        from tool_sandbox.common.tool_discovery import ToolBackend  # type: ignore
        from tool_sandbox.roles.base_role import BaseRole  # type: ignore
        from tool_sandbox.roles.execution_environment import (  # type: ignore
            ExecutionEnvironment,
        )
        from tool_sandbox.scenarios import named_scenarios  # type: ignore
    except ImportError as error:
        raise RuntimeError(
            "ToolSandbox dependencies are unavailable; run inside the "
            "proper-toolsandbox environment"
        ) from error

    random.seed(0)
    scenarios = named_scenarios(preferred_tool_backend=ToolBackend.DEFAULT)
    inventory_records = {
        str(record["name"]): record for record in inventory["records"]
    }
    call_index = 0

    def initialize(scenario: Any) -> Any:
        context = copy.deepcopy(scenario.starting_context)
        set_current_context(context)
        environment = ExecutionEnvironment()
        sandbox = context.get_database(
            DatabaseNamespace.SANDBOX,
            drop_sandbox_message_index=False,
            get_all_history_snapshots=True,
        )
        for row in sandbox.iter_rows(named=True):
            if (
                row["recipient"] == RoleType.EXECUTION_ENVIRONMENT
                and row["sender"] == RoleType.SYSTEM
            ):
                environment.respond(
                    ending_index=int(row["sandbox_message_index"])
                )
        return copy.deepcopy(get_current_context())

    def execute_tool(context: Any, action: Mapping[str, Any]) -> tuple[Any, str | None]:
        nonlocal call_index
        call_index += 1
        set_current_context(copy.deepcopy(context))
        tool = str(action["tool"])
        arguments = dict(action["arguments"])
        call_id = f"call_memory_source_{call_index:04d}"
        code = (
            f"{call_id}_parameters = {arguments!r}\n"
            f"{call_id}_response = {tool}(**{call_id}_parameters)\n"
            f"print(repr({call_id}_response))"
        )
        BaseRole.add_messages(
            [
                Message(
                    sender=RoleType.AGENT,
                    recipient=RoleType.EXECUTION_ENVIRONMENT,
                    content=code,
                    conversation_active=True,
                    openai_tool_call_id=call_id,
                    openai_function_name=tool,
                )
            ]
        )
        ExecutionEnvironment().respond()
        current = copy.deepcopy(get_current_context())
        sandbox = current.get_database(
            DatabaseNamespace.SANDBOX,
            drop_sandbox_message_index=False,
            get_all_history_snapshots=True,
        )
        return current, sandbox[-1]["tool_call_exception"][0]

    def add_final_message(context: Any, content: str) -> Any:
        set_current_context(copy.deepcopy(context))
        BaseRole.add_messages(
            [
                Message(
                    sender=RoleType.AGENT,
                    recipient=RoleType.USER,
                    content=content,
                    conversation_active=True,
                )
            ]
        )
        return copy.deepcopy(get_current_context())

    trajectory_records = []
    raw_cards = []
    for source in config["source_trajectories"]:
        scenario_name = str(source["scenario_name"])
        family = str(source["source_family"])
        if scenario_name not in inventory_records:
            raise RuntimeError(f"source scenario absent from inventory: {scenario_name}")
        if inventory_records[scenario_name]["semantic_family"] != family:
            raise RuntimeError(f"source semantic family mismatch: {scenario_name}")
        scenario = scenarios[scenario_name]
        context = initialize(scenario)
        context, failed_exception = execute_tool(
            context, source["failed_goal_action"]
        )
        required = str(
            source["failed_goal_action"]["required_exception_substring"]
        )
        if failed_exception is None or required not in failed_exception:
            raise RuntimeError(f"required source failure was not observed: {scenario_name}")

        action_records = []
        for recovery_index, action in enumerate(
            source["recovery_actions"], start=1
        ):
            context, exception = execute_tool(context, action)
            action_record = {
                "recovery_index": recovery_index,
                "tool": str(action["tool"]),
                "arguments": dict(action["arguments"]),
                "exception": exception,
                "behavior_signature": behavior_signature(action),
            }
            action_records.append(action_record)
            raw_cards.append(
                {
                    "experience_id": (
                        f"toolsandbox::{family}::action_{recovery_index}"
                    ),
                    "source_scenario": scenario_name,
                    "source_family": family,
                    "source_recovery_index": recovery_index,
                    "natural_text": str(action["natural_text"]),
                    "trigger_evidence": list(action["trigger_evidence"]),
                    "recovery_operation": "invoke_prerequisite",
                    "proposed_action": {
                        "tool_name": str(action["tool"]),
                        "argument_template": dict(action["arguments"]),
                    },
                    "continuation_policy": "verify_then_continue",
                    "success_evidence": [
                        "source_trajectory_similarity:1.0",
                        "source_action_without_exception"
                    ],
                    "stop_conditions": [],
                    "source_tool": str(source["failed_goal_action"]["tool"]),
                    "behavior_signature": behavior_signature(action),
                    "extraction_confidence": 1.0,
                }
            )
        context = add_final_message(context, str(source["final_message"]))
        evaluation = scenario.evaluation.evaluate(
            execution_context=context,
            max_turn_count=scenario.max_messages,
        )
        trajectory_records.append(
            {
                "scenario_name": scenario_name,
                "source_family": family,
                "failed_goal_exception": failed_exception,
                "recovery_actions": action_records,
                "similarity": float(evaluation.similarity),
                "milestone_similarity": float(evaluation.milestone_similarity),
                "minefield_similarity": float(evaluation.minefield_similarity),
            }
        )

    required_similarity = float(
        config["derivation_rule"][
            "require_complete_source_trajectory_similarity"
        ]
    )
    trajectories_passed = all(
        record["similarity"] == required_similarity
        and all(
            action["exception"] is None
            for action in record["recovery_actions"]
        )
        for record in trajectory_records
    )
    if not trajectories_passed:
        raise RuntimeError("source trajectory validation failed")

    # Apply the frozen, source-independent deduplication rule.
    deduplicated = {}
    for card in sorted(raw_cards, key=lambda value: value["experience_id"]):
        deduplicated.setdefault(card["behavior_signature"], card)
    cards = sorted(
        deduplicated.values(), key=lambda value: value["experience_id"]
    )
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_toolsandbox_action_memory_preparation",
        "identities": {
            "config_sha256": sha256_file(config_path),
            "dynamic_inventory_sha256": sha256_file(inventory_path),
            "scripted_smoke_sha256": sha256_file(smoke_path),
        },
        "derivation_rule": dict(config["derivation_rule"]),
        "trajectory_records": trajectory_records,
        "raw_action_card_count": len(raw_cards),
        "deduplicated_action_card_count": len(cards),
        "duplicate_behavior_count": len(raw_cards) - len(cards),
        "memory_cards": cards,
        "source_trajectories_passed": trajectories_passed,
        "model_pilot_authorized": False,
        "boundary": dict(config["boundary"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare action-level memories from scripted source trajectories."
    )
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    config = load_config(args.config)
    result = prepare(args.config)
    output = args.output or ROOT / config["output"]["path"]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "trajectory_records": result["trajectory_records"],
                "raw_action_card_count": result["raw_action_card_count"],
                "deduplicated_action_card_count": result[
                    "deduplicated_action_card_count"
                ],
                "duplicate_behavior_count": result["duplicate_behavior_count"],
                "source_trajectories_passed": result[
                    "source_trajectories_passed"
                ],
                "boundary": result["boundary"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    status = "PASS" if result["source_trajectories_passed"] else "STOP"
    print(f"RESULT={status}_PROPER_V2_TOOLSANDBOX_ACTION_MEMORY_PREPARATION")
    print("NOTE=Only scripted source trajectories were used; no model was loaded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
