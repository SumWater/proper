from __future__ import annotations

import argparse
import copy
import hashlib
import json
import random
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONFIG = (
    ROOT / "configs" / "proper_v2" / "toolsandbox_scripted_smoke.yaml"
)


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if (
        config.get("status")
        != "exploratory_scripted_evaluator_smoke_not_model_experiment"
    ):
        raise RuntimeError("ToolSandbox scripted smoke config has invalid status")
    return config


def context_hash(context: Any) -> str:
    payload = json.dumps(
        context.to_dict(serialize_console=False),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def result_payload(result: Any) -> dict[str, Any]:
    return {
        "similarity": float(result.similarity),
        "milestone_similarity": float(result.milestone_similarity),
        "minefield_similarity": float(result.minefield_similarity),
        "turn_count": int(result.turn_count),
        "milestone_mapping": {
            str(key): list(value)
            for key, value in result.milestone_mapping.items()
        },
        "minefield_mapping": {
            str(key): list(value)
            for key, value in result.minefield_mapping.items()
        },
    }


def run_smoke(config_path: Path = CONFIG) -> dict[str, Any]:
    config = load_config(config_path)
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

    call_index = 0

    def execute_tool(context: Any, action: dict[str, Any]) -> tuple[Any, str | None]:
        nonlocal call_index
        call_index += 1
        set_current_context(copy.deepcopy(context))
        tool = str(action["tool"])
        arguments = dict(action["arguments"])
        call_id = f"call_scripted_{call_index:04d}"
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
        exception = sandbox[-1]["tool_call_exception"][0]
        return current, exception

    def add_agent_message(context: Any, content: str) -> Any:
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

    def evaluate(scenario: Any, context: Any) -> dict[str, Any]:
        result = scenario.evaluation.evaluate(
            execution_context=context,
            max_turn_count=scenario.max_messages,
        )
        return result_payload(result)

    state_config = config["cases"]["state_dependency"]
    state_scenario = scenarios[state_config["scenario_name"]]
    state_initial = initialize(state_scenario)
    failed_context, first_exception = execute_tool(
        state_initial, state_config["common_failed_action"]
    )
    failure_hash = context_hash(failed_context)
    baseline_start = copy.deepcopy(failed_context)
    proper_start = copy.deepcopy(failed_context)
    baseline_start_hash = context_hash(baseline_start)
    proper_start_hash = context_hash(proper_start)

    baseline_context = baseline_start
    baseline_exceptions = []
    for action in state_config["baseline_recovery"]:
        baseline_context, exception = execute_tool(baseline_context, action)
        baseline_exceptions.append(exception)

    proper_context = proper_start
    proper_exceptions = []
    for action in state_config["proper_recovery"]:
        proper_context, exception = execute_tool(proper_context, action)
        proper_exceptions.append(exception)
    proper_context = add_agent_message(
        proper_context, state_config["final_message"]
    )
    baseline_result = evaluate(state_scenario, baseline_context)
    proper_result = evaluate(state_scenario, proper_context)

    info_config = config["cases"]["insufficient_information"]
    info_scenario = scenarios[info_config["scenario_name"]]
    info_initial = initialize(info_scenario)
    info_hash = context_hash(info_initial)
    unsafe_start = copy.deepcopy(info_initial)
    ask_start = copy.deepcopy(info_initial)
    silent_start = copy.deepcopy(info_initial)
    unsafe_start_hash = context_hash(unsafe_start)
    ask_start_hash = context_hash(ask_start)
    silent_start_hash = context_hash(silent_start)
    unsafe_context, unsafe_exception = execute_tool(
        unsafe_start, info_config["unsafe_action"]
    )
    ask_context = add_agent_message(
        ask_start, info_config["safe_ask_message"]
    )
    silent_context = silent_start
    unsafe_result = evaluate(info_scenario, unsafe_context)
    ask_result = evaluate(info_scenario, ask_context)
    silent_result = evaluate(info_scenario, silent_context)
    ask_specificity = ask_result["similarity"] != silent_result["similarity"]

    checks = {
        "required_common_failure_observed": (
            first_exception is not None
            and state_config["common_failed_action"][
                "required_exception_substring"
            ]
            in first_exception
        ),
        "state_dependency_failure_prefix_identical": (
            failure_hash == baseline_start_hash == proper_start_hash
        ),
        "state_dependency_baseline_score_expected": (
            baseline_result["similarity"]
            == float(state_config["expected_baseline_similarity"])
        ),
        "state_dependency_proper_score_expected": (
            proper_result["similarity"]
            == float(state_config["expected_proper_similarity"])
        ),
        "state_dependency_recovery_actions_succeeded": all(
            exception is None for exception in proper_exceptions
        ),
        "insufficient_information_branch_prefix_identical": (
            info_hash
            == unsafe_start_hash
            == ask_start_hash
            == silent_start_hash
        ),
        "insufficient_information_unsafe_score_expected": (
            unsafe_result["similarity"]
            == float(info_config["expected_unsafe_similarity"])
        ),
        "insufficient_information_safe_ask_score_expected": (
            ask_result["similarity"]
            == float(info_config["expected_safe_ask_similarity"])
        ),
        "insufficient_information_silent_stop_score_expected": (
            silent_result["similarity"]
            == float(info_config["expected_silent_stop_similarity"])
        ),
        "native_ask_specificity_matches_protocol": (
            ask_specificity
            == bool(
                info_config[
                    "native_metric_expected_to_distinguish_ask_from_silent_stop"
                ]
            )
        ),
    }
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_toolsandbox_scripted_evaluator_smoke",
        "source_inventory": config["source_inventory"],
        "state_dependency": {
            "scenario_name": state_config["scenario_name"],
            "failure_prefix_sha256": failure_hash,
            "baseline_start_sha256": baseline_start_hash,
            "proper_start_sha256": proper_start_hash,
            "first_exception": first_exception,
            "baseline_exceptions": baseline_exceptions,
            "proper_exceptions": proper_exceptions,
            "baseline_result": baseline_result,
            "proper_result": proper_result,
        },
        "insufficient_information": {
            "scenario_name": info_config["scenario_name"],
            "branch_prefix_sha256": info_hash,
            "unsafe_start_sha256": unsafe_start_hash,
            "safe_ask_start_sha256": ask_start_hash,
            "silent_stop_start_sha256": silent_start_hash,
            "unsafe_action_exception": unsafe_exception,
            "unsafe_result": unsafe_result,
            "safe_ask_result": ask_result,
            "silent_stop_result": silent_result,
            "native_ask_specificity_present": ask_specificity,
        },
        "checks": checks,
        "scripted_smoke_passed": all(checks.values()),
        "interpretation": {
            "state_dependency_evaluator_discriminates_recovery": (
                proper_result["similarity"] > baseline_result["similarity"]
            ),
            "insufficient_information_evaluator_discriminates_unsafe_action": (
                ask_result["similarity"] > unsafe_result["similarity"]
            ),
            "insufficient_information_native_metric_cannot_separate_ask_and_stop": (
                not ask_specificity
            ),
        },
        "boundary": dict(config["boundary"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run scripted ToolSandbox evaluator smoke cases."
    )
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    config = load_config(args.config)
    result = run_smoke(args.config)
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
                "state_dependency": result["state_dependency"],
                "insufficient_information": result["insufficient_information"],
                "checks": result["checks"],
                "interpretation": result["interpretation"],
                "boundary": result["boundary"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    status = "PASS" if result["scripted_smoke_passed"] else "STOP"
    print(f"RESULT={status}_PROPER_V2_TOOLSANDBOX_SCRIPTED_SMOKE")
    print("NOTE=Only scripted actions were used; no model was loaded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
