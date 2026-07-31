from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

try:
    import jsonschema
except ModuleNotFoundError:
    jsonschema = None

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from failure_memory.proper_v2.contracts import (
    DecisionPhase,
    ProposedAction,
    RecoveryOperation,
)
from failure_memory.proper_v2.v2_2 import (
    LifecycleMemorySpec,
    LifecycleObservation,
    LifecyclePolicy,
    LifecycleStatus,
    advance_lifecycle,
    start_lifecycle,
)
from failure_memory.proper_v2.v2_2_1 import (
    ContinuationMode,
    ContinuationPolicy,
    ReviewDisposition,
    continuation_prompt_payload,
    initial_continuation_state,
    record_completed_action,
    review_decision,
)


TRIGGER = "state_dependency:wifi_disabled"
ACTION = ProposedAction("set_wifi_status", {"on": True})


def memory_spec() -> LifecycleMemorySpec:
    return LifecycleMemorySpec(
        experience_id="memory-wifi",
        recovery_operation=RecoveryOperation.INVOKE_PREREQUISITE,
        proposed_action=ACTION,
        trigger_evidence=(TRIGGER,),
        runtime_success_evidence=("action_succeeded",),
    )


class ProperV221ContinuationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.memory = memory_spec()
        self.lifecycle_policy = LifecyclePolicy()
        self.policy = ContinuationPolicy(
            maximum_repeat_replans=2,
            maximum_invalid_replans=1,
            require_completed_action_evidence=True,
        )
        active = start_lifecycle(
            self.memory,
            LifecycleObservation(
                phase=DecisionPhase.POST_FAILURE,
                active_trigger_evidence=(TRIGGER,),
            ),
            self.lifecycle_policy,
        )
        self.active = active
        consumed = advance_lifecycle(
            active,
            self.memory,
            LifecycleObservation(
                phase=DecisionPhase.POST_FAILURE,
                action=ACTION,
                action_succeeded=True,
                evidence_codes=("tool_result:success",),
            ),
            self.lifecycle_policy,
        )
        self.consumed = consumed
        continuation = initial_continuation_state(active, self.policy)
        self.continuation = record_completed_action(
            continuation,
            lifecycle_state=consumed,
            action=ACTION,
            success_evidence=("action_succeeded", "tool_result:success"),
        )

    def test_consumed_repeat_requests_replan_without_execution(self) -> None:
        review = review_decision(
            self.continuation,
            self.consumed,
            self.memory,
            {
                "kind": "tool",
                "tool_name": "set_wifi_status",
                "arguments": {"on": True},
            },
            self.policy,
        )
        self.assertEqual(review.disposition, ReviewDisposition.REPLAN)
        self.assertFalse(review.decision_allowed)
        self.assertEqual(review.state.mode, ContinuationMode.REPLAN_REQUIRED)
        self.assertEqual(review.state.blocked_repeat_count, 1)
        self.assertEqual(review.state.remaining_repeat_replans, 1)
        self.assertIsNone(review.state.stop_reason)

    def test_replanned_ordinary_action_is_allowed(self) -> None:
        blocked = review_decision(
            self.continuation,
            self.consumed,
            self.memory,
            {
                "kind": "tool",
                "tool_name": "set_wifi_status",
                "arguments": {"on": True},
            },
            self.policy,
        )
        accepted = review_decision(
            blocked.state,
            self.consumed,
            self.memory,
            {
                "kind": "tool",
                "tool_name": "search_holiday",
                "arguments": {"holiday_name": "Christmas Day"},
            },
            self.policy,
        )
        self.assertEqual(accepted.disposition, ReviewDisposition.ALLOW)
        self.assertTrue(accepted.decision_allowed)
        self.assertEqual(
            accepted.state.mode,
            ContinuationMode.ORDINARY_TASK_PLANNING,
        )
        self.assertEqual(accepted.state.blocked_repeat_count, 1)
        self.assertEqual(accepted.state.replan_count, 1)

    def test_two_replans_then_stop_on_third_repeat(self) -> None:
        decision = {
            "kind": "tool",
            "tool_name": "set_wifi_status",
            "arguments": {"on": True},
        }
        first = review_decision(
            self.continuation,
            self.consumed,
            self.memory,
            decision,
            self.policy,
        )
        second = review_decision(
            first.state,
            self.consumed,
            self.memory,
            decision,
            self.policy,
        )
        third = review_decision(
            second.state,
            self.consumed,
            self.memory,
            decision,
            self.policy,
        )
        self.assertEqual(second.disposition, ReviewDisposition.REPLAN)
        self.assertEqual(second.state.remaining_repeat_replans, 0)
        self.assertEqual(third.disposition, ReviewDisposition.STOP)
        self.assertEqual(third.state.mode, ContinuationMode.STOPPED)
        self.assertEqual(
            third.reason_code,
            "repeat_replan_budget_exhausted",
        )

    def test_feedback_contains_evidence_but_no_actionable_memory(self) -> None:
        review = review_decision(
            self.continuation,
            self.consumed,
            self.memory,
            {
                "kind": "tool",
                "tool_name": "set_wifi_status",
                "arguments": {"on": True},
            },
            self.policy,
        )
        payload = continuation_prompt_payload(
            review.state,
            blocked_decision={
                "kind": "tool",
                "tool_name": "set_wifi_status",
                "arguments": {"on": True},
            },
        )
        self.assertIsNone(payload["actionable_memory"])
        self.assertEqual(len(payload["completed_actions"]), 1)
        self.assertIn(
            "Choose the next uncompleted step",
            payload["planning_instruction"],
        )

    def test_consumed_repeat_without_success_ledger_stops_closed(self) -> None:
        empty = initial_continuation_state(self.consumed, self.policy)
        review = review_decision(
            empty,
            self.consumed,
            self.memory,
            {
                "kind": "tool",
                "tool_name": "set_wifi_status",
                "arguments": {"on": True},
            },
            self.policy,
        )
        self.assertEqual(review.disposition, ReviewDisposition.STOP)
        self.assertEqual(
            review.reason_code,
            "consumed_repeat_lacks_completed_action_evidence",
        )

    def test_active_recovery_action_remains_allowed(self) -> None:
        active_continuation = initial_continuation_state(
            self.active,
            self.policy,
        )
        review = review_decision(
            active_continuation,
            self.active,
            self.memory,
            {
                "kind": "tool",
                "tool_name": "set_wifi_status",
                "arguments": {"on": True},
            },
            self.policy,
        )
        self.assertEqual(review.disposition, ReviewDisposition.ALLOW)
        self.assertEqual(
            review.state.mode,
            ContinuationMode.MEMORY_GUIDED,
        )

    def test_pre_action_stop_policy_still_blocks_tool(self) -> None:
        stop_memory = LifecycleMemorySpec(
            experience_id="memory-stop",
            recovery_operation=RecoveryOperation.STOP_AND_REPORT,
            proposed_action=None,
            trigger_evidence=("insufficient_information",),
            runtime_success_evidence=("agent_stopped",),
        )
        lifecycle = start_lifecycle(
            stop_memory,
            LifecycleObservation(
                phase=DecisionPhase.PRE_ACTION,
                active_trigger_evidence=("insufficient_information",),
            ),
            self.lifecycle_policy,
        )
        continuation = initial_continuation_state(lifecycle, self.policy)
        review = review_decision(
            continuation,
            lifecycle,
            stop_memory,
            {
                "kind": "tool",
                "tool_name": "unsafe_tool",
                "arguments": {},
            },
            self.policy,
        )
        self.assertEqual(review.disposition, ReviewDisposition.STOP)
        self.assertEqual(
            review.reason_code,
            "active_stop_policy_tool_call_blocked",
        )

    def test_invalid_decision_has_separate_budget(self) -> None:
        first = review_decision(
            self.continuation,
            self.consumed,
            self.memory,
            {"kind": "invalid"},
            self.policy,
        )
        second = review_decision(
            first.state,
            self.consumed,
            self.memory,
            {"kind": "invalid"},
            self.policy,
        )
        self.assertEqual(first.disposition, ReviewDisposition.REPLAN)
        self.assertEqual(second.disposition, ReviewDisposition.STOP)
        self.assertEqual(
            second.reason_code,
            "invalid_replan_budget_exhausted",
        )

    def test_completed_action_is_deduplicated(self) -> None:
        again = record_completed_action(
            self.continuation,
            lifecycle_state=self.consumed,
            action=ACTION,
            success_evidence=("action_succeeded",),
        )
        self.assertEqual(len(again.completed_actions), 1)
        self.assertEqual(again.lifecycle_status, LifecycleStatus.CONSUMED)

    def test_completed_action_rejects_unconsumed_lifecycle(self) -> None:
        active = initial_continuation_state(self.active, self.policy)
        with self.assertRaisesRegex(ValueError, "consumed lifecycle"):
            record_completed_action(
                active,
                lifecycle_state=self.active,
                action=ACTION,
                success_evidence=("action_succeeded",),
            )

    @unittest.skipIf(jsonschema is None, "jsonschema is not installed locally")
    def test_continuation_state_validates_against_schema(self) -> None:
        schema = json.loads(
            (
                ROOT
                / "schemas"
                / "proper_v2"
                / "memory_continuation_v2_2_1.schema.json"
            ).read_text(encoding="utf-8")
        )
        jsonschema.validate(self.continuation.to_mapping(), schema)


if __name__ == "__main__":
    unittest.main()
