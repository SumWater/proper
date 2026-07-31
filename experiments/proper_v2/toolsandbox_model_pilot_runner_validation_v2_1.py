from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
CONFIG = (
    ROOT
    / "configs"
    / "proper_v2"
    / "toolsandbox_model_pilot_runner_validation_v2_1.yaml"
)


def canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    )


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def context_hash(context: Any) -> str:
    return sha256_text(
        json.dumps(
            context.to_dict(serialize_console=False),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
    )


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("status") != "scripted_runner_validation_before_model_outputs":
        raise RuntimeError("runner-validation config status is invalid")
    boundary = config["boundary"]
    if (
        not boundary["scripted_decisions_only"]
        or boundary["model_loaded"]
        or boundary["model_outputs_read"]
        or boundary["gpu_run_authorized"]
    ):
        raise RuntimeError("runner validation cannot authorize model execution")
    return config


def load_manifest(config: Mapping[str, Any]) -> tuple[Path, dict[str, Any]]:
    frozen = config["prepared_manifest"]
    path = ROOT / str(frozen["path"])
    if sha256_file(path) != str(frozen["sha256"]):
        raise RuntimeError("prepared manifest file hash mismatch")
    payload = json.loads(path.read_text(encoding="utf-8"))
    stored = str(payload["identities"].pop("prepared_payload_sha256"))
    observed = sha256_text(canonical(payload))
    payload["identities"]["prepared_payload_sha256"] = stored
    if stored != observed or stored != str(frozen["prepared_payload_sha256"]):
        raise RuntimeError("prepared manifest payload identity mismatch")
    if not payload["ready_for_runner_implementation"]:
        raise RuntimeError("prepared manifest is not runner-ready")
    return path, payload


def parse_content(content: str) -> Any:
    try:
        return ast.literal_eval(content)
    except (SyntaxError, ValueError):
        return content


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


def holiday_dynamic_reference_diagnostic(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    if record["semantic_family"] != "find_days_till_holiday_wifi_off":
        return {"applicable": False, "reproduced": False}
    proper = record["conditions"]["proper_v2_1_memory"]
    try:
        current = next(
            item["result"]
            for item in record["prefix_history"]
            if item["tool_name"] == "get_current_timestamp"
            and item["exception"] is None
        )
        holiday = next(
            item["result"]
            for item in proper["tool_history"]
            if item["tool_name"] == "search_holiday"
            and item["exception"] is None
        )
        diff = next(
            item
            for item in proper["tool_history"]
            if item["tool_name"] == "timestamp_diff"
            and item["exception"] is None
        )
    except StopIteration:
        return {
            "applicable": True,
            "complete_required_trace_present": False,
            "reproduced": False,
        }
    mapping = proper["evaluation"]["milestone_mapping"]
    arguments_exact = (
        abs(float(diff["arguments"]["timestamp_0"]) - float(current)) <= 1.0
        and abs(float(diff["arguments"]["timestamp_1"]) - float(holiday)) <= 1.0
    )
    dynamic_score = float(mapping["3"][1])
    dependent_final_score = float(mapping["4"][1])
    return {
        "applicable": True,
        "timestamp_arguments_reuse_matched_results": arguments_exact,
        "dynamic_timestamp_diff_milestone_score": dynamic_score,
        "dependent_final_answer_milestone_score": dependent_final_score,
        "reproduced": (
            arguments_exact
            and dynamic_score == 0.0
            and dependent_final_score == 1.0
        ),
    }


def synthetic_decision(
    *,
    record: Mapping[str, Any],
    condition: str,
    branch_history: list[dict[str, Any]],
    prefix_history: list[dict[str, Any]],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    phase = str(record["decision_phase"])
    family = str(record["semantic_family"])
    memory = record["conditions"][condition]["memory"]
    if condition == "tfidf_rank1_memory":
        operation = str(memory["recovery_operation"])
        if operation == "stop_and_report":
            return {
                "kind": "stop",
                "reason_code": "synthetic_rank1_stop",
                "message": "Unable to continue safely.",
            }
        if not branch_history:
            action = (
                record["branch_action"]
                if phase == "post_failure"
                else config["synthetic_baseline_actions"][family]
            )
            return {
                "kind": "tool",
                "tool_name": str(action["tool_name"]),
                "arguments": dict(action["arguments"]),
            }
        return {
            "kind": "stop",
            "reason_code": "synthetic_rank1_retry_exhausted",
            "message": "Unable to complete the request.",
        }

    if phase == "pre_action":
        return {
            "kind": "stop",
            "reason_code": "insufficient_information",
            "message": "I cannot safely continue because required information is unavailable.",
        }

    step = len(branch_history)
    proposed = memory["proposed_action"]
    if step == 0:
        return {
            "kind": "tool",
            "tool_name": str(proposed["tool_name"]),
            "arguments": dict(proposed["argument_template"]),
        }
    if family == "find_days_till_holiday_wifi_off":
        if step == 1:
            return {
                "kind": "tool",
                "tool_name": "search_holiday",
                "arguments": {"holiday_name": "Christmas Day", "year": None},
            }
        if step == 2:
            current = next(
                item["result"]
                for item in prefix_history
                if item["tool_name"] == "get_current_timestamp"
            )
            holiday = next(
                item["result"]
                for item in branch_history
                if item["tool_name"] == "search_holiday"
                and item["exception"] is None
            )
            return {
                "kind": "tool",
                "tool_name": "timestamp_diff",
                "arguments": {
                    "timestamp_0": float(current),
                    "timestamp_1": float(holiday),
                },
            }
        diff = next(
            item["result"]
            for item in branch_history
            if item["tool_name"] == "timestamp_diff"
            and item["exception"] is None
        )
        return {
            "kind": "stop",
            "reason_code": "task_complete",
            "message": f"It is {diff['days']} days till Christmas Day",
        }
    if family == "send_message_with_contact_content_cellular_off":
        if step == 1:
            return {
                "kind": "tool",
                "tool_name": "send_message_with_phone_number",
                "arguments": {
                    "phone_number": "+12453344098",
                    "content": "How's the new album coming along",
                },
            }
        return {
            "kind": "stop",
            "reason_code": "task_complete",
            "message": (
                "Your message to Fredrik Thordendal has been sent saying: "
                "How's the new album coming along"
            ),
        }
    if family == "turn_on_location_low_battery_mode":
        if step == 1:
            return {
                "kind": "tool",
                "tool_name": "set_location_service_status",
                "arguments": {"on": True},
            }
        return {
            "kind": "stop",
            "reason_code": "task_complete",
            "message": "Location service has been turned on.",
        }
    raise RuntimeError(f"no synthetic continuation for family: {family}")


def run_validation(
    config_path: Path = CONFIG,
    *,
    decision_provider: Any | None = None,
    pair_ids: set[str] | None = None,
) -> dict[str, Any]:
    config = load_config(config_path)
    manifest_path, manifest = load_manifest(config)
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
    except ImportError as exc:
        raise RuntimeError(
            "ToolSandbox dependencies are unavailable; run inside the "
            "proper-toolsandbox environment"
        ) from exc

    random.seed(0)
    scenarios = named_scenarios(preferred_tool_backend=ToolBackend.DEFAULT)
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

    def execute_tool(
        context: Any,
        *,
        action: Mapping[str, Any],
        allowed_tools: set[str],
    ) -> tuple[Any, dict[str, Any]]:
        nonlocal call_index
        tool_name = str(action["tool_name"])
        if tool_name not in allowed_tools:
            raise RuntimeError(f"synthetic action uses unavailable tool: {tool_name}")
        arguments = dict(action["arguments"])
        call_index += 1
        call_id = f"call_runner_validation_{call_index:04d}"
        set_current_context(copy.deepcopy(context))
        code = (
            f"{call_id}_parameters = {arguments!r}\n"
            f"{call_id}_response = {tool_name}(**{call_id}_parameters)\n"
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
                    openai_function_name=tool_name,
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
        row = sandbox[-1]
        exception = row["tool_call_exception"][0]
        content = str(row["content"][0])
        return current, {
            "tool_name": tool_name,
            "arguments": arguments,
            "result": None if exception is not None else parse_content(content),
            "visible_content": content,
            "exception": exception,
        }

    def add_agent_message(context: Any, content: str) -> Any:
        set_current_context(copy.deepcopy(context))
        BaseRole.add_messages(
            [
                Message(
                    sender=RoleType.AGENT,
                    recipient=RoleType.USER,
                    content=content,
                    conversation_active=False,
                )
            ]
        )
        return copy.deepcopy(get_current_context())

    def evaluate(scenario: Any, context: Any) -> dict[str, Any]:
        return result_payload(
            scenario.evaluation.evaluate(
                execution_context=context,
                max_turn_count=scenario.max_messages,
            )
        )

    def execute_condition(
        *,
        record: Mapping[str, Any],
        condition: str,
        scenario: Any,
        start: Any,
        prefix_history: list[dict[str, Any]],
    ) -> dict[str, Any]:
        current = copy.deepcopy(start)
        allowed_tools = set(str(value) for value in record["available_tool_names"])
        history: list[dict[str, Any]] = []
        decisions = []
        max_decisions = int(manifest["agent_budget"]["maximum_decisions_after_branch"])
        max_tools = int(manifest["agent_budget"]["maximum_tool_calls_after_branch"])
        for _ in range(max_decisions):
            if decision_provider is None:
                decision = synthetic_decision(
                    record=record,
                    condition=condition,
                    branch_history=history,
                    prefix_history=prefix_history,
                    config=config,
                )
            else:
                decision = decision_provider.decide(
                    record=record,
                    condition=condition,
                    branch_history=history,
                    prefix_history=prefix_history,
                    decision_index=len(decisions) + 1,
                    decisions_left=max_decisions - len(decisions),
                    tool_calls_left=max_tools - len(history),
                )
            decisions.append(decision)
            if decision["kind"] == "stop":
                message = str(decision.get("message", ""))
                if message:
                    current = add_agent_message(current, message)
                break
            if len(history) >= max_tools:
                break
            current, tool_result = execute_tool(
                current,
                action={
                    "tool_name": decision["tool_name"],
                    "arguments": decision["arguments"],
                },
                allowed_tools=allowed_tools,
            )
            history.append(tool_result)
        evaluation = evaluate(scenario, current)
        expected = str(record["target_policy_type"])
        first = decisions[0]
        selected_action = record["conditions"]["proper_v2_1_memory"]["memory"][
            "proposed_action"
        ]
        if expected == "stop_and_report":
            first_aligned = first["kind"] == "stop"
        else:
            first_aligned = (
                first["kind"] == "tool"
                and first["tool_name"] == selected_action["tool_name"]
                and first["arguments"] == selected_action["argument_template"]
            )
        repeated = sum(
            history[index]["tool_name"] == history[index - 1]["tool_name"]
            and history[index]["arguments"] == history[index - 1]["arguments"]
            for index in range(1, len(history))
        )
        return {
            "start_sha256": context_hash(start),
            "decisions": decisions,
            "tool_history": history,
            "first_decision_policy_alignment": first_aligned,
            "tool_exception_count": sum(
                item["exception"] is not None for item in history
            ),
            "repeated_identical_tool_call_count": repeated,
            "recovery_decision_count": len(decisions),
            "recovery_tool_call_count": len(history),
            "evaluation": evaluation,
            "final_context_sha256": context_hash(current),
        }

    pair_records = []
    selected_records = [
        record
        for record in manifest["records"]
        if pair_ids is None or str(record["pair_id"]) in pair_ids
    ]
    for record in selected_records:
        scenario = scenarios[str(record["scenario_name"])]
        initial = initialize(scenario)
        prefix_history: list[dict[str, Any]] = []
        branch = initial
        prefix_exception_verified = True
        recipe = record["branch_prefix_recipe"]
        if recipe is not None:
            allowed = set(str(value) for value in record["available_tool_names"])
            for action in recipe["prelude_actions"]:
                branch, result = execute_tool(
                    branch, action=action, allowed_tools=allowed
                )
                prefix_history.append(result)
                if result["exception"] is not None:
                    raise RuntimeError("prefix prelude action failed")
            branch, failure = execute_tool(
                branch,
                action=recipe["failed_action"],
                allowed_tools=allowed,
            )
            prefix_history.append(failure)
            required = str(recipe["required_exception_substring"])
            prefix_exception_verified = (
                failure["exception"] is not None
                and required in str(failure["exception"])
            )
        branch_sha256 = context_hash(branch)
        condition_results = {
            condition: execute_condition(
                record=record,
                condition=condition,
                scenario=scenario,
                start=copy.deepcopy(branch),
                prefix_history=prefix_history,
            )
            for condition in manifest["cohort"]["condition_order"]
        }
        starts = {
            value["start_sha256"] for value in condition_results.values()
        }
        pair_records.append(
            {
                "pair_id": record["pair_id"],
                "scenario_name": record["scenario_name"],
                "semantic_family": record["semantic_family"],
                "decision_phase": record["decision_phase"],
                "branch_prefix_sha256": branch_sha256,
                "prefix_history": prefix_history,
                "prefix_exception_verified": prefix_exception_verified,
                "identical_condition_start": starts == {branch_sha256},
                "conditions": condition_results,
            }
        )

    for item in pair_records:
        item["holiday_dynamic_reference_diagnostic"] = (
            holiday_dynamic_reference_diagnostic(item)
        )

    phase_summary = {}
    for phase in ("post_failure", "pre_action"):
        subset = [item for item in pair_records if item["decision_phase"] == phase]
        if not subset:
            continue
        phase_summary[phase] = {
            "pair_count": len(subset),
            "tfidf_mean_similarity": sum(
                item["conditions"]["tfidf_rank1_memory"]["evaluation"][
                    "similarity"
                ]
                for item in subset
            )
            / len(subset),
            "proper_mean_similarity": sum(
                item["conditions"]["proper_v2_1_memory"]["evaluation"][
                    "similarity"
                ]
                for item in subset
            )
            / len(subset),
            "proper_better_pair_count": sum(
                item["conditions"]["proper_v2_1_memory"]["evaluation"][
                    "similarity"
                ]
                > item["conditions"]["tfidf_rank1_memory"]["evaluation"][
                    "similarity"
                ]
                for item in subset
            ),
        }
    expected = config["expected"]
    expected_similarity = config["checks"][
        "expected_proper_similarity_by_family"
    ]
    checks = {
        "pair_count_frozen": len(pair_records) == int(expected["pair_count"]),
        "condition_count_frozen": sum(
            len(item["conditions"]) for item in pair_records
        )
        == int(expected["condition_count"]),
        "phase_counts_frozen": Counter(
            item["decision_phase"] for item in pair_records
        )
        == {
            "post_failure": int(expected["post_failure_pair_count"]),
            "pre_action": int(expected["pre_action_pair_count"]),
        },
        "all_post_failure_exceptions_verified": all(
            item["prefix_exception_verified"]
            for item in pair_records
            if item["decision_phase"] == "post_failure"
        ),
        "all_condition_starts_identical": all(
            item["identical_condition_start"] for item in pair_records
        ),
        "all_proper_first_decisions_aligned": all(
            item["conditions"]["proper_v2_1_memory"][
                "first_decision_policy_alignment"
            ]
            for item in pair_records
        ),
        "proper_no_minefield": all(
            item["conditions"]["proper_v2_1_memory"]["evaluation"][
                "minefield_similarity"
            ]
            == 0.0
            for item in pair_records
        ),
        "proper_similarity_matches_scripted_expectation": all(
            item["conditions"]["proper_v2_1_memory"]["evaluation"]["similarity"]
            == float(expected_similarity[item["semantic_family"]])
            for item in pair_records
        ),
        "holiday_dynamic_reference_limitation_reproduced": all(
            item["holiday_dynamic_reference_diagnostic"]["reproduced"]
            for item in pair_records
            if item["semantic_family"] == "find_days_till_holiday_wifi_off"
        ),
        "non_holiday_proper_similarity_one": all(
            item["conditions"]["proper_v2_1_memory"]["evaluation"][
                "similarity"
            ]
            == 1.0
            for item in pair_records
            if item["semantic_family"] != "find_days_till_holiday_wifi_off"
        ),
        "phase_stratified_improvement": all(
            value["proper_mean_similarity"] > value["tfidf_mean_similarity"]
            for value in phase_summary.values()
        ),
    }
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_1_toolsandbox_scripted_runner_validation",
        "identities": {
            "config_sha256": sha256_file(config_path),
            "prepared_manifest_sha256": sha256_file(manifest_path),
            "prepared_payload_sha256": manifest["identities"][
                "prepared_payload_sha256"
            ],
        },
        "summary": {
            "pair_count": len(pair_records),
            "condition_count": sum(
                len(item["conditions"]) for item in pair_records
            ),
            "phase_summary": phase_summary,
            "validation_checks": checks,
            "runner_validation_passed": all(checks.values()),
            "gpu_run_authorized": False,
        },
        "records": pair_records,
        "boundary": dict(config["boundary"]),
        "interpretation_limits": {
            "scripted_decisions_are_not_model_outputs": True,
            "scripted_effect_is_not_selector_effect_evidence": True,
            "runner_validation_only": True,
            "holiday_native_similarity_ceiling_in_this_runner_is_0_8": True,
            "raw_native_scores_are_not_rewritten": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the phase-aware ToolSandbox multi-step runner."
    )
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    config = load_config(args.config)
    result = run_validation(args.config)
    output = args.output or ROOT / str(config["output"]["path"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2, sort_keys=True))
    status = "PASS" if result["summary"]["runner_validation_passed"] else "STOP"
    print(f"RESULT={status}_PROPER_V2_1_TOOLSANDBOX_RUNNER_VALIDATION")
    print("NOTE=Only scripted decisions were used; no model was loaded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
