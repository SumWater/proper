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
from failure_memory.proper_v2.v2_2 import EvidenceStatus, TriggerStatus
from failure_memory.proper_v2.v2_3 import (
    ActionEffectClass,
    ActionEffectContract,
    ActionExecutionLedger,
    ActionPurpose,
    ActionSpec,
    BudgetPolicy,
    ControllerDisposition,
    ExecutionStatus,
    initial_controller_state,
    observe_execution,
    review_action_proposal,
    review_invalid_decision,
    stop_for_agent_decision,
)
from scripted_traces_v2_3 import (
    _consumed_start,
    _record,
    read_only_contract,
    side_effect_contract,
    state_setting_contract,
)
from failure_memory.proper_v2 import RetrySafety


class ProperV23ControllerTests(unittest.TestCase):
    def test_successful_non_idempotent_repeat_is_never_executed(self) -> None:
        state, ledger, _ = _consumed_start("controller-message")
        action = ActionSpec("send_message", {"recipient": "a", "text": "one"})
        ledger, first = review_action_proposal(
            state=state,
            ledger=ledger,
            action=action,
            effect_contract=side_effect_contract(),
            purpose=ActionPurpose.ORDINARY_TASK,
        )
        assert first.ledger_entry_id is not None
        ledger = _record(
            ledger,
            first.ledger_entry_id,
            ExecutionStatus.SUCCEEDED,
            step=2,
            code="message_sent",
        )
        state = observe_execution(
            state=first.state,
            ledger=ledger,
            entry_id=first.ledger_entry_id,
        )
        ledger, repeat = review_action_proposal(
            state=state,
            ledger=ledger,
            action=action,
            effect_contract=side_effect_contract(),
            purpose=ActionPurpose.ORDINARY_TASK,
        )
        self.assertEqual(repeat.disposition, ControllerDisposition.REPLAN)
        self.assertFalse(repeat.decision_allowed)
        self.assertEqual(
            len(
                [
                    item
                    for item in ledger.entries
                    if item.normalized_identity == action.identity
                    and item.status == ExecutionStatus.SUCCEEDED
                ]
            ),
            1,
        )

    def test_successful_idempotent_setting_is_also_not_repeated(self) -> None:
        state, ledger, action = _consumed_start("controller-state-setting")
        ledger, repeat = review_action_proposal(
            state=state,
            ledger=ledger,
            action=action,
            effect_contract=state_setting_contract(),
            purpose=ActionPurpose.ORDINARY_TASK,
        )
        self.assertEqual(repeat.disposition, ControllerDisposition.REPLAN)
        self.assertFalse(repeat.decision_allowed)

    def test_unknown_side_effect_outcome_requires_read_only_verification(self) -> None:
        state, ledger, _ = _consumed_start("controller-unknown")
        action = ActionSpec("send_message", {"recipient": "a", "text": "one"})
        ledger, first = review_action_proposal(
            state=state,
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
        ledger, wrong = review_action_proposal(
            state=state,
            ledger=ledger,
            action=action,
            effect_contract=side_effect_contract(),
            purpose=ActionPurpose.ORDINARY_TASK,
        )
        self.assertEqual(wrong.disposition, ControllerDisposition.VERIFY)
        self.assertFalse(wrong.decision_allowed)
        verifier = ActionSpec("get_receipt", {"recipient": "a"})
        ledger, allowed = review_action_proposal(
            state=wrong.state,
            ledger=ledger,
            action=verifier,
            effect_contract=read_only_contract(),
            purpose=ActionPurpose.VERIFICATION,
            verifies_entry_id=first.ledger_entry_id,
        )
        self.assertEqual(allowed.disposition, ControllerDisposition.VERIFY)
        self.assertTrue(allowed.decision_allowed)

    def test_failed_retry_uses_only_retry_budget(self) -> None:
        action = ActionSpec("lookup", {"id": "x"})
        state = initial_controller_state(
            phase=DecisionPhase.POST_FAILURE,
            selected_memory_experience_id="memory::lookup",
            memory_operation=RecoveryOperation.RETRY_SAME_ACTION,
            memory_action=action,
            budget_policy=BudgetPolicy(
                maximum_retries=1,
                maximum_verifications=2,
                maximum_invalid_decisions=3,
                maximum_replans=4,
            ),
        )
        ledger = ActionExecutionLedger("controller-retry")
        ledger, first = review_action_proposal(
            state=state,
            ledger=ledger,
            action=action,
            effect_contract=read_only_contract(),
            purpose=ActionPurpose.RECOVERY,
        )
        assert first.ledger_entry_id is not None
        ledger = _record(
            ledger,
            first.ledger_entry_id,
            ExecutionStatus.FAILED,
            step=1,
            code="transient_failure",
        )
        state = observe_execution(
            state=first.state,
            ledger=ledger,
            entry_id=first.ledger_entry_id,
            trigger_status=TriggerStatus.HOLDS,
            success_evidence_status=EvidenceStatus.VIOLATED,
        )
        ledger, retry = review_action_proposal(
            state=state,
            ledger=ledger,
            action=action,
            effect_contract=read_only_contract(),
            purpose=ActionPurpose.RECOVERY,
        )
        self.assertTrue(retry.decision_allowed)
        self.assertEqual(retry.state.budgets.remaining_retries, 0)
        self.assertEqual(retry.state.budgets.remaining_verifications, 2)
        self.assertEqual(retry.state.budgets.remaining_invalid_decisions, 3)
        self.assertEqual(retry.state.budgets.remaining_replans, 4)

    def test_invalid_budget_does_not_consume_general_replan_budget(self) -> None:
        state = initial_controller_state(
            phase=DecisionPhase.PRE_ACTION,
            selected_memory_experience_id="memory::ask",
            memory_operation=RecoveryOperation.REQUEST_INFORMATION,
            memory_action=None,
            budget_policy=BudgetPolicy(maximum_invalid_decisions=1, maximum_replans=2),
        )
        first = review_invalid_decision(state)
        self.assertEqual(first.disposition, ControllerDisposition.REPLAN)
        self.assertEqual(first.state.budgets.remaining_invalid_decisions, 0)
        self.assertEqual(first.state.budgets.remaining_replans, 2)
        second = review_invalid_decision(first.state)
        self.assertEqual(second.disposition, ControllerDisposition.STOP)

    def test_unknown_effect_fails_closed_before_execution(self) -> None:
        state, ledger, _ = _consumed_start("controller-unknown-effect")
        contract = ActionEffectContract(
            effect_class=ActionEffectClass.UNKNOWN_EFFECT,
            classification_evidence=("tool_schema:effect_not_declared",),
            retry_safety=RetrySafety.UNKNOWN,
        )
        ledger, review = review_action_proposal(
            state=state,
            ledger=ledger,
            action=ActionSpec("opaque_tool", {"value": 1}),
            effect_contract=contract,
            purpose=ActionPurpose.ORDINARY_TASK,
        )
        self.assertEqual(review.disposition, ControllerDisposition.STOP)
        self.assertFalse(review.decision_allowed)
        with self.assertRaises(ValueError):
            ledger.mark_executed(review.ledger_entry_id or "")

    def test_same_action_cannot_change_effect_contract(self) -> None:
        state, ledger, _ = _consumed_start("controller-contract-change")
        action = ActionSpec("external_action", {"value": "x"})
        ledger, first = review_action_proposal(
            state=state,
            ledger=ledger,
            action=action,
            effect_contract=side_effect_contract(),
            purpose=ActionPurpose.ORDINARY_TASK,
        )
        self.assertTrue(first.decision_allowed)
        ledger, changed = review_action_proposal(
            state=first.state,
            ledger=ledger,
            action=action,
            effect_contract=read_only_contract(),
            purpose=ActionPurpose.ORDINARY_TASK,
        )
        self.assertEqual(changed.disposition, ControllerDisposition.STOP)
        self.assertEqual(changed.reason_code, "action_effect_contract_changed")

    def test_visible_failure_evidence_can_strengthen_unknown_retry_safety(self) -> None:
        action = ActionSpec("lookup", {"id": "x"})
        state = initial_controller_state(
            phase=DecisionPhase.POST_FAILURE,
            selected_memory_experience_id="memory::dynamic-retry",
            memory_operation=RecoveryOperation.RETRY_SAME_ACTION,
            memory_action=action,
            budget_policy=BudgetPolicy(maximum_retries=1),
        )
        initial_contract = ActionEffectContract(
            effect_class=ActionEffectClass.READ_ONLY,
            classification_evidence=("tool_schema:read_only",),
            retry_safety=RetrySafety.UNKNOWN,
        )
        ledger = ActionExecutionLedger("controller-dynamic-retry")
        ledger, first = review_action_proposal(
            state=state,
            ledger=ledger,
            action=action,
            effect_contract=initial_contract,
            purpose=ActionPurpose.RECOVERY,
        )
        assert first.ledger_entry_id is not None
        ledger = _record(
            ledger,
            first.ledger_entry_id,
            ExecutionStatus.FAILED,
            step=1,
            code="failure:no_side_effect_committed",
        )
        state = observe_execution(
            state=first.state,
            ledger=ledger,
            entry_id=first.ledger_entry_id,
            trigger_status=TriggerStatus.HOLDS,
            success_evidence_status=EvidenceStatus.VIOLATED,
        )
        strengthened = ActionEffectContract(
            effect_class=ActionEffectClass.READ_ONLY,
            classification_evidence=("tool_schema:read_only",),
            retry_safety=RetrySafety.SAFE,
            retry_safety_evidence=("tool_result:no_side_effect_committed",),
        )
        ledger, retry = review_action_proposal(
            state=state,
            ledger=ledger,
            action=action,
            effect_contract=strengthened,
            purpose=ActionPurpose.RECOVERY,
        )
        self.assertTrue(retry.decision_allowed)
        self.assertEqual(retry.state.budgets.remaining_retries, 0)

    def test_successful_verification_action_cannot_repeat(self) -> None:
        state, ledger, _ = _consumed_start("controller-verifier-repeat")
        action = ActionSpec("external_action", {"value": "x"})
        ledger, first = review_action_proposal(
            state=state,
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
        verifier = ActionSpec("query_status", {"value": "x"})
        ledger, verification = review_action_proposal(
            state=state,
            ledger=ledger,
            action=verifier,
            effect_contract=read_only_contract(),
            purpose=ActionPurpose.VERIFICATION,
            verifies_entry_id=first.ledger_entry_id,
        )
        assert verification.ledger_entry_id is not None
        ledger = _record(
            ledger,
            verification.ledger_entry_id,
            ExecutionStatus.SUCCEEDED,
            step=3,
            code="status_read",
        )
        ledger, repeated = review_action_proposal(
            state=verification.state,
            ledger=ledger,
            action=verifier,
            effect_contract=read_only_contract(),
            purpose=ActionPurpose.VERIFICATION,
            verifies_entry_id=first.ledger_entry_id,
        )
        self.assertEqual(repeated.disposition, ControllerDisposition.REPLAN)
        self.assertFalse(repeated.decision_allowed)

    def test_agent_stop_transitions_to_stopped_with_reason(self) -> None:
        state = initial_controller_state(
            phase=DecisionPhase.PRE_ACTION,
            selected_memory_experience_id="memory::stop",
            memory_operation=RecoveryOperation.STOP_AND_REPORT,
            memory_action=None,
            budget_policy=BudgetPolicy(),
        )
        stopped = stop_for_agent_decision(state, reason_code="missing_information")
        self.assertEqual(stopped.lifecycle_status.value, "stopped")
        self.assertEqual(stopped.stop_reason, "agent_stop:missing_information")


if __name__ == "__main__":
    unittest.main()
