from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
EXPERIMENTS = ROOT / "experiments" / "proper_v2_3"
for path in (SRC, EXPERIMENTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from failure_memory.proper_v2 import DecisionPhase, RecoveryOperation
from failure_memory.proper_v2.v2_2 import (
    EvidenceStatus,
    LifecycleStatus,
    TriggerStatus,
)
from failure_memory.proper_v2.v2_3 import (
    ActionExecutionLedger,
    ActionPurpose,
    ActionSpec,
    BudgetPolicy,
    ControllerDisposition,
    EvidenceRecord,
    EvidenceSource,
    ExecutionStatus,
    initial_controller_state,
    observe_execution,
    resolve_verification,
    review_action_proposal,
    stop_for_task_completion,
)
from scripted_traces_v2_3 import (
    _consumed_start,
    _record,
    read_only_contract,
    side_effect_contract,
    state_setting_contract,
)


class ProperV23LifecycleBudgetTests(unittest.TestCase):
    def test_memory_success_consumes_and_hands_off(self) -> None:
        state, _, _ = _consumed_start("lifecycle-consumed")
        self.assertEqual(state.lifecycle_status, LifecycleStatus.CONSUMED)
        self.assertEqual(state.planning_mode.value, "ordinary_task_planning")

    def test_success_trigger_conflict_fails_closed(self) -> None:
        action = ActionSpec("set_state", {"enabled": True})
        state = initial_controller_state(
            phase=DecisionPhase.POST_FAILURE,
            selected_memory_experience_id="memory::state",
            memory_operation=RecoveryOperation.INVOKE_PREREQUISITE,
            memory_action=action,
            budget_policy=BudgetPolicy(),
        )
        ledger = ActionExecutionLedger("lifecycle-conflict")
        ledger, review = review_action_proposal(
            state=state,
            ledger=ledger,
            action=action,
            effect_contract=state_setting_contract(),
            purpose=ActionPurpose.RECOVERY,
        )
        assert review.ledger_entry_id is not None
        ledger = _record(
            ledger,
            review.ledger_entry_id,
            ExecutionStatus.SUCCEEDED,
            step=1,
            code="state_set",
        )
        failed = observe_execution(
            state=review.state,
            ledger=ledger,
            entry_id=review.ledger_entry_id,
            trigger_status=TriggerStatus.HOLDS,
            success_evidence_status=EvidenceStatus.SATISFIED,
        )
        self.assertEqual(failed.lifecycle_status, LifecycleStatus.FAILED)
        self.assertEqual(
            failed.stop_reason,
            "success_evidence_conflicts_with_active_trigger",
        )

    def test_unknown_outcome_without_verification_path_fails_closed(self) -> None:
        action = ActionSpec("lookup", {"id": "x"})
        state = initial_controller_state(
            phase=DecisionPhase.POST_FAILURE,
            selected_memory_experience_id="memory::lookup",
            memory_operation=RecoveryOperation.RETRY_SAME_ACTION,
            memory_action=action,
            budget_policy=BudgetPolicy(),
        )
        contract = read_only_contract(verification_supported=False)
        ledger = ActionExecutionLedger("lifecycle-unknown")
        ledger, review = review_action_proposal(
            state=state,
            ledger=ledger,
            action=action,
            effect_contract=contract,
            purpose=ActionPurpose.RECOVERY,
        )
        assert review.ledger_entry_id is not None
        ledger = _record(
            ledger,
            review.ledger_entry_id,
            ExecutionStatus.OUTCOME_UNKNOWN,
            step=1,
            code="response_lost",
        )
        failed = observe_execution(
            state=review.state,
            ledger=ledger,
            entry_id=review.ledger_entry_id,
        )
        self.assertEqual(failed.lifecycle_status, LifecycleStatus.FAILED)

    def test_verification_budget_exhaustion_stops(self) -> None:
        state, ledger, _ = _consumed_start("verification-exhaustion")
        action = ActionSpec("send_message", {"recipient": "a", "text": "once"})
        zero_verification_state = state.__class__(
            **{
                **state.__dict__,
                "budgets": state.budgets.__class__(
                    remaining_retries=state.budgets.remaining_retries,
                    remaining_verifications=0,
                    remaining_invalid_decisions=(
                        state.budgets.remaining_invalid_decisions
                    ),
                    remaining_replans=state.budgets.remaining_replans,
                ),
            }
        )
        ledger, first = review_action_proposal(
            state=zero_verification_state,
            ledger=ledger,
            action=action,
            effect_contract=side_effect_contract(),
            purpose=ActionPurpose.ORDINARY_TASK,
        )
        assert first.ledger_entry_id is not None
        ledger = _record(
            ledger,
            first.ledger_entry_id,
            ExecutionStatus.OUTCOME_UNKNOWN,
            step=2,
            code="response_lost",
        )
        state = observe_execution(
            state=first.state,
            ledger=ledger,
            entry_id=first.ledger_entry_id,
        )
        ledger, stopped = review_action_proposal(
            state=state,
            ledger=ledger,
            action=ActionSpec("get_receipt", {"recipient": "a"}),
            effect_contract=read_only_contract(),
            purpose=ActionPurpose.VERIFICATION,
            verifies_entry_id=first.ledger_entry_id,
        )
        self.assertEqual(stopped.disposition, ControllerDisposition.STOP)
        self.assertEqual(stopped.reason_code, "verification_budget_exhausted")

    def test_replan_budget_exhaustion_stops_repeated_success(self) -> None:
        state, ledger, action = _consumed_start("replan-exhaustion")
        state = state.__class__(
            **{
                **state.__dict__,
                "budgets": state.budgets.__class__(
                    remaining_retries=state.budgets.remaining_retries,
                    remaining_verifications=state.budgets.remaining_verifications,
                    remaining_invalid_decisions=(
                        state.budgets.remaining_invalid_decisions
                    ),
                    remaining_replans=1,
                ),
            }
        )
        ledger, first = review_action_proposal(
            state=state,
            ledger=ledger,
            action=action,
            effect_contract=state_setting_contract(),
            purpose=ActionPurpose.ORDINARY_TASK,
        )
        self.assertEqual(first.disposition, ControllerDisposition.REPLAN)
        ledger, second = review_action_proposal(
            state=first.state,
            ledger=ledger,
            action=action,
            effect_contract=state_setting_contract(),
            purpose=ActionPurpose.ORDINARY_TASK,
        )
        self.assertEqual(second.disposition, ControllerDisposition.STOP)
        self.assertIn("replan_budget_exhausted", second.reason_code)

    def test_retry_budget_exhaustion_prevents_third_execution(self) -> None:
        action = ActionSpec("lookup", {"id": "x"})
        state = initial_controller_state(
            phase=DecisionPhase.POST_FAILURE,
            selected_memory_experience_id="memory::lookup",
            memory_operation=RecoveryOperation.RETRY_SAME_ACTION,
            memory_action=action,
            budget_policy=BudgetPolicy(maximum_retries=1),
        )
        ledger = ActionExecutionLedger("retry-exhaustion")
        for step in (1, 2):
            ledger, review = review_action_proposal(
                state=state,
                ledger=ledger,
                action=action,
                effect_contract=read_only_contract(),
                purpose=ActionPurpose.RECOVERY,
            )
            self.assertTrue(review.decision_allowed)
            assert review.ledger_entry_id is not None
            ledger = _record(
                ledger,
                review.ledger_entry_id,
                ExecutionStatus.FAILED,
                step=step,
                code="transient_failure",
            )
            state = observe_execution(
                state=review.state,
                ledger=ledger,
                entry_id=review.ledger_entry_id,
                trigger_status=TriggerStatus.HOLDS,
                success_evidence_status=EvidenceStatus.VIOLATED,
            )
        ledger, third = review_action_proposal(
            state=state,
            ledger=ledger,
            action=action,
            effect_contract=read_only_contract(),
            purpose=ActionPurpose.RECOVERY,
        )
        self.assertFalse(third.decision_allowed)
        self.assertEqual(third.state.budgets.remaining_retries, 0)

    def test_ordinary_action_verification_does_not_change_consumed_memory(self) -> None:
        state, ledger, _ = _consumed_start("ordinary-verification")
        action = ActionSpec("send_message", {"recipient": "a", "text": "once"})
        ledger, review = review_action_proposal(
            state=state,
            ledger=ledger,
            action=action,
            effect_contract=side_effect_contract(),
            purpose=ActionPurpose.ORDINARY_TASK,
        )
        assert review.ledger_entry_id is not None
        ledger = _record(
            ledger,
            review.ledger_entry_id,
            ExecutionStatus.OUTCOME_UNKNOWN,
            step=2,
            code="response_lost",
        )
        state = observe_execution(
            state=review.state,
            ledger=ledger,
            entry_id=review.ledger_entry_id,
        )
        ledger = ledger.record_outcome(
            review.ledger_entry_id,
            status=ExecutionStatus.SUCCEEDED,
            evidence=(
                EvidenceRecord(
                    EvidenceSource.PUBLIC_STATE,
                    "delivery_receipt_found",
                    3,
                ),
            ),
        )
        resolved = resolve_verification(
            state=state,
            ledger=ledger,
            verified_entry_id=review.ledger_entry_id,
            verified_status=ExecutionStatus.SUCCEEDED,
        )
        self.assertEqual(resolved.lifecycle_status, LifecycleStatus.CONSUMED)
        self.assertIsNone(resolved.verification_required_for_entry_id)

    def test_task_completion_transitions_to_stopped(self) -> None:
        state, _, _ = _consumed_start("task-completion")
        stopped = stop_for_task_completion(state)
        self.assertEqual(stopped.lifecycle_status, LifecycleStatus.STOPPED)
        self.assertEqual(stopped.stop_reason, "task_complete")

    def test_violated_success_evidence_beats_trigger_clearance(self) -> None:
        action = ActionSpec("set_state", {"enabled": True})
        state = initial_controller_state(
            phase=DecisionPhase.POST_FAILURE,
            selected_memory_experience_id="memory::state-violation",
            memory_operation=RecoveryOperation.INVOKE_PREREQUISITE,
            memory_action=action,
            budget_policy=BudgetPolicy(),
        )
        ledger = ActionExecutionLedger("lifecycle-evidence-violation")
        ledger, review = review_action_proposal(
            state=state,
            ledger=ledger,
            action=action,
            effect_contract=state_setting_contract(),
            purpose=ActionPurpose.RECOVERY,
        )
        assert review.ledger_entry_id is not None
        ledger = _record(
            ledger,
            review.ledger_entry_id,
            ExecutionStatus.SUCCEEDED,
            step=1,
            code="state_set",
        )
        failed = observe_execution(
            state=review.state,
            ledger=ledger,
            entry_id=review.ledger_entry_id,
            trigger_status=TriggerStatus.CLEARED,
            success_evidence_status=EvidenceStatus.VIOLATED,
        )
        self.assertEqual(failed.lifecycle_status, LifecycleStatus.FAILED)
        self.assertEqual(failed.stop_reason, "runtime_success_evidence_violated")


if __name__ == "__main__":
    unittest.main()
