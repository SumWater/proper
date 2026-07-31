from __future__ import annotations

import argparse
import copy
import json
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
CONFIG = (
    ROOT
    / "configs"
    / "proper_v2"
    / "toolsandbox_qwen_continuation_development_v2_2_1.yaml"
)
sys.path.insert(0, str(ROOT / "experiments" / "proper_v2"))

import continuation_development_v2_2_1 as continuation  # noqa: E402
import lifecycle_development_v2_2 as lifecycle  # noqa: E402
import toolsandbox_continuation_development_v2_2_1 as scripted  # noqa: E402
import toolsandbox_model_pilot_runner_validation_v2_1 as engine  # noqa: E402
import toolsandbox_qwen_lifecycle_development_v2_2 as qwen_v2_2  # noqa: E402
from failure_memory.proper_v2.v2_2 import (  # noqa: E402
    LifecycleObservation,
    LifecycleStatus,
    PlanningMode,
    advance_lifecycle,
)
from failure_memory.proper_v2.v2_2_1 import (  # noqa: E402
    ContinuationMode,
    ReviewDisposition,
    continuation_prompt_payload,
    initial_continuation_state,
    record_completed_action,
    review_decision,
)
from toolsandbox_qwen_pilot_v2_1 import parse_model_decision  # noqa: E402


CONDITION_REPORT_NAMES = {
    "tfidf_rank1_memory": "tfidf_persistent_memory",
    "proper_v2_1_memory": "proper_persistent_memory",
    "proper_lifecycle_prompt_only": "proper_lifecycle_prompt_only",
    "proper_lifecycle_replan_controller": (
        "proper_lifecycle_replan_controller"
    ),
}
LIFECYCLE_CONDITIONS = {
    "proper_lifecycle_prompt_only",
    "proper_lifecycle_replan_controller",
}
CONTROLLER_CONDITION = "proper_lifecycle_replan_controller"


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("status") != (
        "frozen_qwen_continuation_development_before_model_outputs"
    ):
        raise RuntimeError("v2.2.1 Qwen continuation config status is invalid")
    boundary = config["boundary"]
    if (
        not boundary["gpu_development_run_authorized"]
        or boundary["confirmatory_claim_authorized"]
        or boundary["heldout_claim_authorized"]
        or not boundary["existing_model_exposed_pairs"]
    ):
        raise RuntimeError("Qwen continuation run must remain development-only")
    for item in config["frozen_inputs"].values():
        target = ROOT / str(item["path"])
        observed = continuation.sha256_file(target)
        if observed != str(item["sha256"]):
            raise RuntimeError(
                f"frozen Qwen continuation input mismatch: {target}; "
                f"expected={item['sha256']} observed={observed}"
            )
    return config


class ContinuationQwenProvider:
    def __init__(
        self,
        *,
        client: qwen_v2_2.JsonlWorkerClient,
        config: Mapping[str, Any],
        stage_config: Mapping[str, Any],
    ) -> None:
        self.client = client
        self.config = config
        self.lifecycle_policy = continuation.lifecycle_policy(stage_config)
        self.continuation_policy = continuation.continuation_policy(
            stage_config
        )
        self.call_count = 0
        self.continuation_states = {}

    @staticmethod
    def visible_history(
        history: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return [
            {
                "tool_name": item["tool_name"],
                "arguments": item["arguments"],
                "result": item["result"],
                "exception": item["exception"],
            }
            for item in history
        ]

    @staticmethod
    def lifecycle_messages(
        initial: Mapping[str, Any],
        payload: Mapping[str, Any],
    ) -> list[dict[str, str]]:
        messages = copy.deepcopy(initial["messages"])
        messages[0]["content"] += (
            " Obey MEMORY_LIFECYCLE_STATE. Apply active recovery memory only "
            "until visible success evidence. After consumption, the memory is "
            "removed and ordinary planning for the original task resumes."
        )
        lines = [
            line
            for line in messages[-1]["content"].splitlines()
            if not line.startswith("RETRIEVED_MEMORY=")
        ]
        lines.insert(
            max(0, len(lines) - 2),
            "MEMORY_LIFECYCLE_STATE=" + engine.canonical(payload),
        )
        messages[-1]["content"] = "\n".join(lines)
        return messages

    def _sync_continuation_state(
        self,
        *,
        key: tuple[str, str],
        memory: Any,
        lifecycle_state: Any,
        branch_history: list[dict[str, Any]],
    ):
        previous = self.continuation_states.get(key)
        if previous is None:
            state = initial_continuation_state(
                lifecycle_state,
                self.continuation_policy,
            )
        else:
            if lifecycle_state.planning_mode == PlanningMode.MEMORY_GUIDED:
                mode = ContinuationMode.MEMORY_GUIDED
                stop_reason = None
            elif (
                lifecycle_state.planning_mode
                == PlanningMode.ORDINARY_TASK_PLANNING
            ):
                mode = ContinuationMode.ORDINARY_TASK_PLANNING
                stop_reason = None
            else:
                mode = ContinuationMode.STOPPED
                stop_reason = "terminal_lifecycle"
            state = replace(
                previous,
                lifecycle_status=lifecycle_state.status,
                lifecycle_transition_index=lifecycle_state.transition_index,
                mode=mode,
                feedback_codes=(),
                stop_reason=stop_reason,
            )
        if (
            lifecycle_state.status == LifecycleStatus.CONSUMED
            and memory.proposed_action is not None
            and not state.completed_actions
        ):
            for item in branch_history:
                if (
                    str(item["tool_name"])
                    == memory.proposed_action.tool_name
                    and dict(item["arguments"])
                    == dict(memory.proposed_action.argument_template)
                    and item.get("exception") is None
                ):
                    state = record_completed_action(
                        state,
                        lifecycle_state=lifecycle_state,
                        action=memory.proposed_action,
                        success_evidence=(
                            "action_succeeded",
                            "tool_result:success",
                        ),
                    )
                    break
        self.continuation_states[key] = state
        return state

    def _model_attempt(
        self,
        *,
        record: Mapping[str, Any],
        condition: str,
        messages: list[dict[str, str]],
        decision_index: int,
        attempt_index: int,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        self.call_count += 1
        label = CONDITION_REPORT_NAMES[condition]
        request_id = (
            f"{record['pair_id']}:{label}:step-{decision_index:02d}:"
            f"attempt-{attempt_index:02d}"
        )
        request = {
            "request_id": request_id,
            "messages": messages,
            "seed": int(self.config["model"]["seed"]),
            "max_new_tokens": int(self.config["model"]["max_new_tokens"]),
        }
        response = self.client.complete(request)
        proposed, valid, error = parse_model_decision(
            str(response["raw_text"]),
            available_tools=set(
                str(value) for value in record["available_tool_names"]
            ),
        )
        model = {
            "request_id": request_id,
            "request_sha256": engine.sha256_text(engine.canonical(request)),
            "raw_text": str(response["raw_text"]),
            "valid_json_decision": valid,
            "parse_error": error,
            "usage": dict(response["usage"]),
        }
        print(
            "MODEL_PROGRESS="
            f"{self.call_count} request={request_id} "
            f"valid_json={str(valid).lower()} kind={proposed['kind']}",
            file=sys.stderr,
            flush=True,
        )
        return proposed, model

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
        initial = record["conditions"][condition]["initial_request"]
        memory = None
        lifecycle_state = None
        continuation_state = None
        if condition in LIFECYCLE_CONDITIONS:
            memory, lifecycle_state = lifecycle.state_from_history(
                record,
                branch_history,
                self.lifecycle_policy,
            )
            messages = self.lifecycle_messages(
                initial,
                lifecycle.lifecycle_prompt_payload(
                    lifecycle_state,
                    memory,
                ),
            )
            if condition == CONTROLLER_CONDITION:
                continuation_state = self._sync_continuation_state(
                    key=(str(record["pair_id"]), condition),
                    memory=memory,
                    lifecycle_state=lifecycle_state,
                    branch_history=branch_history,
                )
        else:
            messages = copy.deepcopy(initial["messages"])

        runtime = {
            "visible_prefix_history": self.visible_history(prefix_history),
            "visible_recovery_history": self.visible_history(branch_history),
            "decision_index": decision_index,
            "remaining_budget": {
                "accepted_decisions_left": decisions_left,
                "tool_calls_left": tool_calls_left,
            },
        }
        messages[-1]["content"] += (
            "\nRUNTIME_VISIBLE_HISTORY=" + engine.canonical(runtime)
        )

        attempts = []
        blocked_attempts = []
        attempt_index = 0
        final_review = None
        while True:
            attempt_index += 1
            proposed, model = self._model_attempt(
                record=record,
                condition=condition,
                messages=messages,
                decision_index=decision_index,
                attempt_index=attempt_index,
            )
            attempts.append(model)
            if condition != CONTROLLER_CONDITION:
                decision = dict(proposed)
                break

            assert memory is not None
            assert lifecycle_state is not None
            assert continuation_state is not None
            reviewed_decision = proposed if model["valid_json_decision"] else {
                "kind": "invalid"
            }
            final_review = review_decision(
                continuation_state,
                lifecycle_state,
                memory,
                reviewed_decision,
                self.continuation_policy,
            )
            continuation_state = final_review.state
            self.continuation_states[
                (str(record["pair_id"]), condition)
            ] = continuation_state
            if final_review.disposition == ReviewDisposition.ALLOW:
                decision = dict(proposed)
                break
            if final_review.disposition == ReviewDisposition.STOP:
                decision = {
                    "kind": "stop",
                    "reason_code": final_review.reason_code,
                    "message": (
                        "The continuation controller stopped after a bounded "
                        "safety or replan condition."
                    ),
                }
                break

            blocked_attempts.append(
                {
                    "proposed_decision": dict(proposed),
                    "valid_json_decision": bool(
                        model["valid_json_decision"]
                    ),
                    "review": final_review.to_mapping(),
                }
            )
            replan_payload = continuation_prompt_payload(
                continuation_state,
                blocked_decision=proposed,
            )
            messages = self.lifecycle_messages(
                initial,
                lifecycle.lifecycle_prompt_payload(
                    lifecycle_state,
                    memory,
                ),
            )
            messages[0]["content"] += (
                " CONTINUATION_REPLAN_STATE is execution feedback, not "
                "retrieved memory. The blocked action was not executed."
            )
            messages[-1]["content"] += (
                "\nRUNTIME_VISIBLE_HISTORY=" + engine.canonical(runtime)
                + "\nCONTINUATION_REPLAN_STATE="
                + engine.canonical(replan_payload)
            )

        if lifecycle_state is not None:
            if decision["kind"] == "stop" and (
                lifecycle_state.status == LifecycleStatus.ACTIVE
            ):
                lifecycle_state = advance_lifecycle(
                    lifecycle_state,
                    memory,
                    LifecycleObservation(
                        phase=lifecycle_state.phase,
                        agent_stop_reason=str(decision["reason_code"]),
                    ),
                    self.lifecycle_policy,
                )
            decision["_lifecycle"] = lifecycle_state.to_mapping()
            decision["_lifecycle_prompt_sha256"] = engine.sha256_text(
                engine.canonical(
                    lifecycle.lifecycle_prompt_payload(
                        lifecycle_state,
                        memory,
                    )
                )
            )
        if condition == CONTROLLER_CONDITION:
            assert continuation_state is not None
            decision["_continuation"] = continuation_state.to_mapping()
            decision["_controller"] = {
                "guard_applied": True,
                "decision_allowed": (
                    final_review is not None
                    and final_review.decision_allowed
                ),
                "final_disposition": (
                    final_review.disposition.value
                    if final_review is not None
                    else None
                ),
                "final_reason_code": (
                    final_review.reason_code
                    if final_review is not None
                    else None
                ),
                "blocked_attempts": blocked_attempts,
                "model_proposed_decision": dict(proposed),
            }
        else:
            decision["_controller"] = {
                "guard_applied": False,
                "decision_allowed": True,
                "final_disposition": "allow",
                "final_reason_code": "controller_not_enabled",
                "blocked_attempts": [],
                "model_proposed_decision": dict(proposed),
            }
        decision["_model"] = attempts[-1]
        decision["_model_attempts"] = attempts
        return decision


def _attempts(condition: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        attempt
        for decision in condition["decisions"]
        for attempt in decision.get(
            "_model_attempts",
            [decision["_model"]],
        )
    ]


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    phase_summary = {}
    for phase in ("pre_action", "post_failure"):
        subset = [item for item in records if item["decision_phase"] == phase]
        phase_summary[phase] = {}
        for condition_name, report_name in CONDITION_REPORT_NAMES.items():
            conditions = [
                item["conditions"][condition_name] for item in subset
            ]
            attempts = [
                attempt
                for condition in conditions
                for attempt in _attempts(condition)
            ]
            decisions = [
                decision
                for condition in conditions
                for decision in condition["decisions"]
            ]
            blocked_attempts = [
                blocked
                for decision in decisions
                for blocked in decision["_controller"]["blocked_attempts"]
            ]
            phase_summary[phase][report_name] = {
                "mean_similarity": sum(
                    item["evaluation"]["similarity"] for item in conditions
                )
                / len(conditions),
                "task_completion_count": sum(
                    item["evaluation"]["similarity"] == 1.0
                    for item in conditions
                ),
                "first_decision_alignment_count": sum(
                    item["first_decision_policy_alignment"]
                    for item in conditions
                ),
                "minefield_condition_count": sum(
                    item["evaluation"]["minefield_similarity"] > 0
                    for item in conditions
                ),
                "tool_exception_count": sum(
                    item["tool_exception_count"] for item in conditions
                ),
                "executed_identical_tool_call_count": sum(
                    item["repeated_identical_tool_call_count"]
                    for item in conditions
                ),
                "accepted_decision_count": sum(
                    item["recovery_decision_count"] for item in conditions
                ),
                "tool_call_count": sum(
                    item["recovery_tool_call_count"] for item in conditions
                ),
                "model_request_count": len(attempts),
                "valid_json_model_request_count": sum(
                    bool(item["valid_json_decision"]) for item in attempts
                ),
                "invalid_json_model_request_count": sum(
                    not bool(item["valid_json_decision"]) for item in attempts
                ),
                "prompt_token_count": sum(
                    int(item["usage"]["prompt_token_count"])
                    for item in attempts
                ),
                "completion_token_count": sum(
                    int(item["usage"]["completion_token_count"])
                    for item in attempts
                ),
                "blocked_proposal_count": len(blocked_attempts),
                "blocked_completed_action_repeat_count": sum(
                    item["review"]["reason_code"]
                    == "consumed_action_repeat_replan_required"
                    for item in blocked_attempts
                ),
                "replan_accepted_decision_count": sum(
                    bool(decision["_controller"]["blocked_attempts"])
                    and decision["_controller"]["final_disposition"] == "allow"
                    for decision in decisions
                ),
                "replan_budget_exhaustion_count": sum(
                    decision.get("reason_code")
                    in {
                        "repeat_replan_budget_exhausted",
                        "invalid_replan_budget_exhausted",
                    }
                    for decision in decisions
                ),
                "lifecycle_consumed_condition_count": sum(
                    any(
                        decision.get("_lifecycle", {}).get("status")
                        == "consumed"
                        for decision in item["decisions"]
                    )
                    for item in conditions
                ),
            }
    all_attempts = [
        attempt
        for record in records
        for condition in record["conditions"].values()
        for attempt in _attempts(condition)
    ]
    return {
        "pair_count": len(records),
        "condition_count": sum(len(item["conditions"]) for item in records),
        "phase_counts": dict(
            sorted(Counter(item["decision_phase"] for item in records).items())
        ),
        "all_condition_starts_identical": all(
            item["identical_condition_start"] for item in records
        ),
        "model_request_count": len(all_attempts),
        "valid_json_model_request_count": sum(
            bool(item["valid_json_decision"]) for item in all_attempts
        ),
        "invalid_json_model_request_count": sum(
            not bool(item["valid_json_decision"]) for item in all_attempts
        ),
        "phase_summary": phase_summary,
    }


def run_development(config_path: Path = CONFIG) -> dict[str, Any]:
    config = load_config(config_path)
    stage_config_path = ROOT / str(
        config["frozen_inputs"]["scripted_continuation_config"]["path"]
    )
    print(
        "STAGE=scripted_continuation_validation",
        file=sys.stderr,
        flush=True,
    )
    scripted_result = scripted.dynamic_validation(stage_config_path)
    if not scripted_result["passed"]:
        raise RuntimeError(
            "same-process continuation validation failed; GPU not started"
        )
    stage_config = continuation.load_config(stage_config_path)
    manifest = continuation.load_manifest(stage_config)
    runner_config = ROOT / str(
        config["frozen_inputs"]["continuation_runner_config"]["path"]
    )
    pair_order = [str(item["pair_id"]) for item in manifest["records"]]
    smoke_pair = str(config["execution"]["smoke_pair_id"])
    print("STAGE=load_qwen_worker", file=sys.stderr, flush=True)
    with qwen_v2_2.JsonlWorkerClient(config) as client:
        provider = ContinuationQwenProvider(
            client=client,
            config=config,
            stage_config=stage_config,
        )
        print(f"STAGE=gpu_smoke pair={smoke_pair}", file=sys.stderr, flush=True)
        smoke = engine.run_validation(
            runner_config,
            decision_provider=provider,
            pair_ids={smoke_pair},
        )
        smoke_record = smoke["records"][0] if smoke["records"] else None
        smoke_attempts = (
            [
                attempt
                for condition in smoke_record["conditions"].values()
                for attempt in _attempts(condition)
            ]
            if smoke_record is not None
            else []
        )
        smoke_passed = (
            smoke_record is not None
            and smoke_record["identical_condition_start"]
            and all(
                bool(attempt["valid_json_decision"])
                for attempt in smoke_attempts
            )
        )
        if not smoke_passed:
            return {
                "schema_version": 1,
                "run_kind": "proper_v2_2_1_qwen_continuation_smoke_stopped",
                "smoke_passed": False,
                "full_development_completed": False,
                "scripted_continuation_summary": scripted_result["summary"],
                "smoke_records": smoke["records"],
                "model_request_log": client.requests,
                "boundary": dict(config["boundary"]),
            }
        remaining = set(pair_order) - {smoke_pair}
        print(
            f"STAGE=full_development remaining_pairs={len(remaining)}",
            file=sys.stderr,
            flush=True,
        )
        remainder = engine.run_validation(
            runner_config,
            decision_provider=provider,
            pair_ids=remaining,
        )
        by_id = {
            str(item["pair_id"]): item
            for item in smoke["records"] + remainder["records"]
        }
        records = [by_id[pair_id] for pair_id in pair_order]
        summary = summarize(records)
        completed = (
            summary["pair_count"] == int(config["execution"]["pair_count"])
            and summary["condition_count"]
            == int(config["execution"]["condition_count"])
            and summary["all_condition_starts_identical"]
            and summary["invalid_json_model_request_count"] == 0
            and summary["model_request_count"] == len(client.requests)
        )
        return {
            "schema_version": 1,
            "run_kind": (
                "proper_v2_2_1_toolsandbox_qwen_continuation_development"
            ),
            "identities": {
                "config_sha256": continuation.sha256_file(config_path),
                "frozen_input_sha256": {
                    name: str(item["sha256"])
                    for name, item in config["frozen_inputs"].items()
                },
            },
            "smoke_pair_id": smoke_pair,
            "smoke_passed": True,
            "full_development_completed": completed,
            "scripted_continuation_summary": scripted_result["summary"],
            "summary": summary,
            "records": records,
            "model_request_log": client.requests,
            "model_protocol": dict(config["model"]),
            "boundary": dict(config["boundary"]),
            "interpretation_limits": {
                "v2_1_pairs_are_development_only": True,
                "four_conditions_isolate_development_endpoints": True,
                "selector_first_step_reported_separately": True,
                "memory_lifecycle_reported_separately": True,
                "continuation_reported_separately": True,
                "final_task_completion_reported_separately": True,
                "safety_reported_separately": True,
                "cost_reported_separately": True,
                "blocked_model_attempts_included_in_cost": True,
                "confirmatory_claim_not_authorized": True,
                "all_agent_memory_generalization_not_authorized": True,
            },
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run frozen four-condition Qwen continuation development."
    )
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    config = load_config(args.config)
    result = run_development(args.config)
    output = args.output or ROOT / str(config["output"]["path"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "run_kind",
                    "smoke_pair_id",
                    "smoke_passed",
                    "full_development_completed",
                    "summary",
                    "interpretation_limits",
                )
                if key in result
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    print(f"OUTPUT={output}")
    status = "PASS" if result.get("full_development_completed") else "STOP"
    print(f"RESULT={status}_PROPER_V2_2_1_QWEN_CONTINUATION_DEVELOPMENT")
    return 0 if result.get("full_development_completed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
