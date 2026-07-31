from __future__ import annotations

import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from failure_memory.proper_v2.contracts import (
    DecisionPhase,
    ProposedAction,
    RecoveryOperation,
)
from failure_memory.proper_v2.v2_2 import (
    EvidenceStatus,
    ExposureMode,
    LifecycleMemorySpec,
    LifecycleObservation,
    LifecyclePolicy,
    LifecycleStatus,
    PlanningMode,
    TriggerStatus,
    advance_lifecycle,
    guard_decision,
    lifecycle_prompt_payload,
    start_lifecycle,
)


TRIGGER = "state_dependency:wifi_disabled"
ACTION = ProposedAction("set_wifi_status", {"on": True})


def prerequisite_memory() -> LifecycleMemorySpec:
    return LifecycleMemorySpec(
        experience_id="memory-wifi",
        recovery_operation=RecoveryOperation.INVOKE_PREREQUISITE,
        proposed_action=ACTION,
        trigger_evidence=(TRIGGER,),
        runtime_success_evidence=("action_succeeded",),
        declared_success_evidence=("source_action_without_exception",),
        natural_text="Enable wifi, then continue the original task.",
    )


def start_observation(
    phase: DecisionPhase = DecisionPhase.POST_FAILURE,
) -> LifecycleObservation:
    return LifecycleObservation(
        phase=phase,
        active_trigger_evidence=(TRIGGER,),
    )


class ProperV22LifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.memory = prerequisite_memory()
        self.policy = LifecyclePolicy(
            maximum_application_attempts=2,
            consumed_memory_weight=0.0,
            require_success_evidence=True,
            stop_on_success_trigger_conflict=True,
        )

    def test_start_is_active_for_both_decision_phases(self) -> None:
        for phase in (DecisionPhase.PRE_ACTION, DecisionPhase.POST_FAILURE):
            with self.subTest(phase=phase.value):
                state = start_lifecycle(
                    self.memory,
                    start_observation(phase),
                    self.policy,
                )
                self.assertEqual(state.phase, phase)
                self.assertEqual(state.status, LifecycleStatus.ACTIVE)
                self.assertEqual(state.trigger_status, TriggerStatus.HOLDS)
                self.assertEqual(state.planning_mode, PlanningMode.MEMORY_GUIDED)
                self.assertEqual(state.exposure_mode, ExposureMode.FULL)

    def test_success_consumes_memory_and_returns_to_ordinary_planning(self) -> None:
        state = start_lifecycle(
            self.memory,
            start_observation(),
            self.policy,
        )
        state = advance_lifecycle(
            state,
            self.memory,
            LifecycleObservation(
                phase=DecisionPhase.POST_FAILURE,
                action=ACTION,
                action_succeeded=True,
                evidence_codes=("tool_result:success",),
            ),
            self.policy,
        )
        self.assertEqual(state.status, LifecycleStatus.CONSUMED)
        self.assertEqual(
            state.success_evidence_status,
            EvidenceStatus.SATISFIED,
        )
        self.assertEqual(
            state.planning_mode,
            PlanningMode.ORDINARY_TASK_PLANNING,
        )
        self.assertEqual(state.exposure_mode, ExposureMode.REMOVED)
        self.assertEqual(state.injection_weight, 0.0)
        self.assertIsNone(
            lifecycle_prompt_payload(state, self.memory)["memory"]
        )

    def test_explicit_trigger_clear_consumes_without_reapplying_action(self) -> None:
        state = start_lifecycle(
            self.memory,
            start_observation(),
            self.policy,
        )
        state = advance_lifecycle(
            state,
            self.memory,
            LifecycleObservation(
                phase=DecisionPhase.POST_FAILURE,
                cleared_trigger_evidence=(TRIGGER,),
            ),
            self.policy,
        )
        self.assertEqual(state.status, LifecycleStatus.CONSUMED)
        self.assertEqual(state.trigger_status, TriggerStatus.CLEARED)
        self.assertEqual(state.application_attempt_count, 0)

    def test_success_with_still_active_trigger_fails_closed(self) -> None:
        state = start_lifecycle(
            self.memory,
            start_observation(),
            self.policy,
        )
        state = advance_lifecycle(
            state,
            self.memory,
            LifecycleObservation(
                phase=DecisionPhase.POST_FAILURE,
                active_trigger_evidence=(TRIGGER,),
                action=ACTION,
                action_succeeded=True,
            ),
            self.policy,
        )
        self.assertEqual(state.status, LifecycleStatus.FAILED)
        self.assertEqual(state.planning_mode, PlanningMode.STOPPED)
        self.assertIn(
            "success_evidence_conflicts_with_active_trigger",
            state.reason_codes,
        )

    def test_failure_retries_once_then_exhausts_budget(self) -> None:
        state = start_lifecycle(
            self.memory,
            start_observation(),
            self.policy,
        )
        failure = LifecycleObservation(
            phase=DecisionPhase.POST_FAILURE,
            active_trigger_evidence=(TRIGGER,),
            action=ACTION,
            action_succeeded=False,
            evidence_codes=("tool_exception",),
        )
        state = advance_lifecycle(
            state,
            self.memory,
            failure,
            self.policy,
        )
        self.assertEqual(state.status, LifecycleStatus.ACTIVE)
        self.assertEqual(state.remaining_application_attempts, 1)
        state = advance_lifecycle(
            state,
            self.memory,
            failure,
            self.policy,
        )
        self.assertEqual(state.status, LifecycleStatus.FAILED)
        self.assertEqual(state.remaining_application_attempts, 0)
        self.assertEqual(state.failed_attempt_count, 2)
        self.assertEqual(state.exposure_mode, ExposureMode.REMOVED)

    def test_consumed_action_repeat_is_blocked_but_ordinary_tool_is_allowed(
        self,
    ) -> None:
        state = start_lifecycle(
            self.memory,
            start_observation(),
            self.policy,
        )
        state = advance_lifecycle(
            state,
            self.memory,
            LifecycleObservation(
                phase=DecisionPhase.POST_FAILURE,
                action=ACTION,
                action_succeeded=True,
            ),
            self.policy,
        )
        allowed, reason = guard_decision(
            state,
            self.memory,
            {
                "kind": "tool",
                "tool_name": "set_wifi_status",
                "arguments": {"on": True},
            },
        )
        self.assertFalse(allowed)
        self.assertEqual(reason, "consumed_memory_action_repeat_blocked")
        allowed, reason = guard_decision(
            state,
            self.memory,
            {
                "kind": "tool",
                "tool_name": "search_holiday",
                "arguments": {"holiday_name": "Christmas Day"},
            },
        )
        self.assertTrue(allowed)
        self.assertEqual(reason, "tool_decision_allowed")

    def test_stop_memory_blocks_tool_and_transitions_on_agent_stop(self) -> None:
        memory = LifecycleMemorySpec(
            experience_id="memory-stop",
            recovery_operation=RecoveryOperation.STOP_AND_REPORT,
            proposed_action=None,
            trigger_evidence=("insufficient_information",),
            runtime_success_evidence=("agent_stopped",),
            stop_conditions=(),
        )
        observation = LifecycleObservation(
            phase=DecisionPhase.PRE_ACTION,
            active_trigger_evidence=("insufficient_information",),
        )
        state = start_lifecycle(memory, observation, self.policy)
        allowed, reason = guard_decision(
            state,
            memory,
            {"kind": "tool", "tool_name": "unsafe_tool", "arguments": {}},
        )
        self.assertFalse(allowed)
        self.assertEqual(reason, "active_stop_policy_tool_call_blocked")
        state = advance_lifecycle(
            state,
            memory,
            LifecycleObservation(
                phase=DecisionPhase.PRE_ACTION,
                agent_stop_reason="insufficient_information",
            ),
            self.policy,
        )
        self.assertEqual(state.status, LifecycleStatus.STOPPED)
        self.assertEqual(
            state.success_evidence_status,
            EvidenceStatus.SATISFIED,
        )

    def test_terminal_state_is_stable(self) -> None:
        state = start_lifecycle(
            self.memory,
            start_observation(),
            self.policy,
        )
        state = advance_lifecycle(
            state,
            self.memory,
            LifecycleObservation(
                phase=DecisionPhase.POST_FAILURE,
                action=ACTION,
                action_succeeded=True,
            ),
            self.policy,
        )
        again = advance_lifecycle(
            state,
            self.memory,
            start_observation(),
            self.policy,
        )
        self.assertEqual(again.status, LifecycleStatus.CONSUMED)
        self.assertEqual(again.application_attempt_count, 1)
        self.assertIn("terminal_state_is_stable", again.reason_codes)

    def test_observation_rejects_trigger_contradiction(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "cannot be active and cleared",
        ):
            LifecycleObservation(
                phase=DecisionPhase.POST_FAILURE,
                active_trigger_evidence=(TRIGGER,),
                cleared_trigger_evidence=(TRIGGER,),
            )

    def test_demoted_mode_removes_actionable_memory_content(self) -> None:
        policy = LifecyclePolicy(
            maximum_application_attempts=2,
            consumed_memory_weight=0.1,
            require_success_evidence=True,
            stop_on_success_trigger_conflict=True,
        )
        state = start_lifecycle(
            self.memory,
            start_observation(),
            policy,
        )
        state = advance_lifecycle(
            state,
            self.memory,
            LifecycleObservation(
                phase=DecisionPhase.POST_FAILURE,
                action=ACTION,
                action_succeeded=True,
            ),
            policy,
        )
        prompt = lifecycle_prompt_payload(state, self.memory)
        self.assertEqual(state.exposure_mode, ExposureMode.DEMOTED)
        self.assertTrue(prompt["memory"]["actionable_content_removed"])
        self.assertNotIn("proposed_action", prompt["memory"])


if __name__ == "__main__":
    unittest.main()
