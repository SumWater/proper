"""Five-condition provider: frozen v2.2.1 behavior plus v2.3 trajectory guard."""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT / "experiments" / "proper_v2", ROOT / "experiments" / "proper_v2_3"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import lifecycle_development_v2_2 as lifecycle  # noqa: E402
import toolsandbox_model_pilot_runner_validation_v2_1 as engine  # noqa: E402
from failure_memory.proper_v2.v2_3 import ControllerDisposition  # noqa: E402
from toolsandbox_qwen_continuation_development_v2_2_1 import (  # noqa: E402
    ContinuationQwenProvider,
)
from toolsandbox_qwen_pilot_v2_1 import parse_model_decision  # noqa: E402
from toolsandbox_five_condition_runner_adapter_v2_3 import (  # noqa: E402
    FIFTH_CONDITION, ExecutionAwareTrajectoryGuard, PublicEffectRegistry,
    canonical,
)


class FiveConditionProvider(ContinuationQwenProvider):
    def __init__(
        self,
        *,
        client: Any,
        config: Mapping[str, Any],
        stage_config: Mapping[str, Any],
        method_config: Mapping[str, Any],
        prompts: Mapping[str, Any],
        effect_registry: PublicEffectRegistry,
    ) -> None:
        super().__init__(client=client, config=config, stage_config=stage_config)
        self.method_config = method_config
        self.prompts = prompts
        self.effect_registry = effect_registry
        self.guards: dict[str, ExecutionAwareTrajectoryGuard] = {}
        self.source_records: dict[str, Mapping[str, Any]] = {}

    def _fifth_model_attempt(
        self,
        *,
        record: Mapping[str, Any],
        messages: list[dict[str, str]],
        decision_index: int,
        attempt_index: int,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        self.call_count += 1
        request_id = (
            f"{record['pair_id']}:proper_v2_3_full_action_ledger_controller:"
            f"step-{decision_index:02d}:attempt-{attempt_index:02d}"
        )
        request = {
            "request_id": request_id, "messages": messages,
            "seed": int(self.config["model"]["seed"]),
            "max_new_tokens": int(self.config["model"]["max_new_tokens"]),
        }
        response = self.client.complete(request)
        proposed, valid, error = parse_model_decision(
            str(response["raw_text"]),
            available_tools=set(str(value) for value in record["available_tool_names"]),
        )
        model = {
            "request_id": request_id,
            "request_sha256": engine.sha256_text(engine.canonical(request)),
            "raw_text": str(response["raw_text"]),
            "valid_json_decision": valid, "parse_error": error,
            "usage": dict(response["usage"]),
        }
        print(
            f"MODEL_PROGRESS={self.call_count} request={request_id} "
            f"valid_json={str(valid).lower()} kind={proposed['kind']}",
            file=sys.stderr, flush=True,
        )
        return proposed, model

    def _base_messages(
        self,
        *,
        initial: Mapping[str, Any],
        memory: Any,
        lifecycle_state: Any,
        runtime: Mapping[str, Any],
        feedback: Mapping[str, Any] | None = None,
    ) -> list[dict[str, str]]:
        messages = self.lifecycle_messages(
            initial, lifecycle.lifecycle_prompt_payload(lifecycle_state, memory)
        )
        messages[0]["content"] += (
            " EXECUTION_CONTROLLER_FEEDBACK is observable execution state, not retrieved memory."
        )
        messages[-1]["content"] += "\nRUNTIME_VISIBLE_HISTORY=" + engine.canonical(runtime)
        if feedback is not None:
            disposition = str(feedback["controller_disposition"])
            instructions = self.prompts["controller_feedback"]
            if disposition == "verify":
                instruction = instructions["verify_instruction"]
            elif str(feedback["reason_code"]).startswith("invalid_decision"):
                instruction = instructions["invalid_decision_instruction"]
            else:
                instruction = instructions["replan_instruction"]
            messages[-1]["content"] += (
                "\nEXECUTION_CONTROLLER_FEEDBACK=" + canonical(feedback)
                + "\nEXECUTION_CONTROLLER_INSTRUCTION=" + instruction
            )
        return messages

    def decide(self, **kwargs: Any) -> dict[str, Any]:
        if kwargs["condition"] != FIFTH_CONDITION:
            return super().decide(**kwargs)
        record = kwargs["record"]
        branch_history = kwargs["branch_history"]
        prefix_history = kwargs["prefix_history"]
        pair_id = str(record["pair_id"])
        self.source_records[pair_id] = record
        initial = record["conditions"][FIFTH_CONDITION]["initial_request"]
        memory, lifecycle_state = lifecycle.state_from_history(
            record, branch_history, self.lifecycle_policy,
        )
        guard = self.guards.get(pair_id)
        if guard is None:
            guard = ExecutionAwareTrajectoryGuard(
                record=record, config=self.method_config,
                effect_registry=self.effect_registry, prefix_history=prefix_history,
            )
            self.guards[pair_id] = guard
        guard.sync_history(branch_history, lifecycle_state)
        runtime = {
            "visible_prefix_history": self.visible_history(prefix_history),
            "visible_recovery_history": self.visible_history(branch_history),
            "decision_index": kwargs["decision_index"],
            "remaining_budget": {
                "accepted_decisions_left": kwargs["decisions_left"],
                "tool_calls_left": kwargs["tool_calls_left"],
            },
        }
        messages = self._base_messages(
            initial=initial, memory=memory, lifecycle_state=lifecycle_state,
            runtime=runtime,
        )
        attempts: list[dict[str, Any]] = []
        blocked: list[dict[str, Any]] = []
        attempt_index = 0
        while True:
            attempt_index += 1
            proposed, model = self._fifth_model_attempt(
                record=record, messages=messages,
                decision_index=int(kwargs["decision_index"]),
                attempt_index=attempt_index,
            )
            attempts.append(model)
            review = guard.review(proposed, valid=bool(model["valid_json_decision"]))
            decision = review["decision"]
            if proposed.get("kind") == "stop" and model["valid_json_decision"]:
                final = dict(proposed)
                break
            if decision is not None and decision.decision_allowed:
                final = dict(proposed)
                break
            if decision is None or decision.disposition == ControllerDisposition.STOP:
                final = {
                    "kind": "stop",
                    "reason_code": guard.runtime.state.stop_reason or "controller_stop",
                    "message": "The execution controller stopped the trajectory safely.",
                }
                break
            feedback = guard.feedback_payload(review=review, proposed=proposed)
            blocked_item = {
                "proposed_decision": dict(proposed),
                "valid_json_decision": bool(model["valid_json_decision"]),
                "review": decision.to_mapping(),
                "feedback_sha256": engine.sha256_text(canonical(feedback)),
            }
            blocked.append(blocked_item)
            guard.runtime.blocked_attempts.append(copy.deepcopy(blocked_item))
            messages = self._base_messages(
                initial=initial, memory=memory, lifecycle_state=lifecycle_state,
                runtime=runtime, feedback=feedback,
            )
        final["_lifecycle"] = lifecycle_state.to_mapping()
        final["_controller"] = {
            "guard_applied": True,
            "decision_allowed": bool(
                final.get("kind") == "tool" and decision is not None and decision.decision_allowed
            ),
            "final_disposition": (
                decision.disposition.value if decision is not None else "stop"
            ),
            "final_reason_code": (
                decision.reason_code if decision is not None else guard.runtime.state.stop_reason
            ),
            "blocked_attempts": blocked,
            "model_proposed_decision": dict(proposed),
            "execution_guard_snapshot": guard.snapshot(),
        }
        final["_model"] = attempts[-1]
        final["_model_attempts"] = attempts
        return final

    def finalize_records(self, records: list[dict[str, Any]]) -> None:
        for record in records:
            pair_id = str(record["pair_id"])
            condition = record["conditions"][FIFTH_CONDITION]
            guard = self.guards[pair_id]
            source_record = self.source_records[pair_id]
            memory, lifecycle_state = lifecycle.state_from_history(
                source_record, condition["tool_history"], self.lifecycle_policy,
            )
            del memory
            snapshot, safety = guard.finalize_summary(
                history=condition["tool_history"],
                lifecycle_state=lifecycle_state,
            )
            condition["action_execution_guard"] = snapshot
            condition["execution_safety"] = safety
