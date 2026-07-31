from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from failure_memory.proper_v2 import DecisionPhase, RetrySafety
from failure_memory.proper_v2.v2_3 import (
    ActionEffectClass,
    ActionEffectContract,
    ActionExecutionLedger,
    ActionPurpose,
    ActionSpec,
    ControllerDisposition,
    EvidenceRecord,
    EvidenceSource,
    ExecutionStatus,
    LedgerEntry,
)


def _contract() -> ActionEffectContract:
    return ActionEffectContract(
        effect_class=ActionEffectClass.NON_IDEMPOTENT_SIDE_EFFECT,
        classification_evidence=("tool_schema:external_side_effect",),
        retry_safety=RetrySafety.UNSAFE,
        retry_safety_evidence=("public_contract:duplicate_possible",),
        verification_supported=True,
        verification_evidence=("tool_schema:receipt_query",),
    )


class ProperV23LedgerTests(unittest.TestCase):
    def test_ledger_records_complete_status_progression(self) -> None:
        ledger = ActionExecutionLedger("trajectory")
        ledger, entry = ledger.append_proposal(
            action=ActionSpec("send_message", {"text": "hello"}),
            effect_contract=_contract(),
            phase=DecisionPhase.POST_FAILURE,
            purpose=ActionPurpose.ORDINARY_TASK,
            disposition=ControllerDisposition.ALLOW,
            decision_allowed=True,
            reason_codes=("new_action_allowed",),
        )
        ledger = ledger.mark_executed(entry.entry_id)
        ledger = ledger.record_outcome(
            entry.entry_id,
            status=ExecutionStatus.SUCCEEDED,
            evidence=(
                EvidenceRecord(
                    EvidenceSource.TOOL_RESULT,
                    "message_sent",
                    1,
                ),
            ),
        )
        self.assertEqual(ledger.entry(entry.entry_id).status, ExecutionStatus.SUCCEEDED)
        self.assertEqual(ledger.to_mapping()["entries"][0]["sequence_index"], 0)

    def test_unknown_outcome_can_only_resolve_once(self) -> None:
        ledger = ActionExecutionLedger("trajectory")
        ledger, entry = ledger.append_proposal(
            action=ActionSpec("send_message", {"text": "hello"}),
            effect_contract=_contract(),
            phase=DecisionPhase.POST_FAILURE,
            purpose=ActionPurpose.ORDINARY_TASK,
            disposition=ControllerDisposition.ALLOW,
            decision_allowed=True,
            reason_codes=("new_action_allowed",),
        )
        ledger = ledger.mark_executed(entry.entry_id)
        ledger = ledger.record_outcome(
            entry.entry_id,
            status=ExecutionStatus.OUTCOME_UNKNOWN,
            evidence=(
                EvidenceRecord(EvidenceSource.TOOL_RESULT, "response_lost", 1),
            ),
        )
        ledger = ledger.record_outcome(
            entry.entry_id,
            status=ExecutionStatus.SUCCEEDED,
            evidence=(
                EvidenceRecord(EvidenceSource.PUBLIC_STATE, "receipt_found", 2),
            ),
        )
        with self.assertRaises(ValueError):
            ledger.record_outcome(
                entry.entry_id,
                status=ExecutionStatus.FAILED,
                evidence=(),
            )

    def test_blocked_proposal_is_recorded_but_cannot_execute(self) -> None:
        ledger = ActionExecutionLedger("trajectory")
        ledger, entry = ledger.append_proposal(
            action=ActionSpec("send_message", {"text": "hello"}),
            effect_contract=_contract(),
            phase=DecisionPhase.POST_FAILURE,
            purpose=ActionPurpose.ORDINARY_TASK,
            disposition=ControllerDisposition.REPLAN,
            decision_allowed=False,
            reason_codes=("repeat_blocked",),
        )
        self.assertEqual(len(ledger.entries), 1)
        with self.assertRaises(ValueError):
            ledger.mark_executed(entry.entry_id)

    def test_sequence_indices_and_ids_are_deterministic(self) -> None:
        action = ActionSpec("lookup", {"id": "x"})
        first = ActionExecutionLedger("same")
        second = ActionExecutionLedger("same")
        args = dict(
            action=action,
            effect_contract=_contract(),
            phase=DecisionPhase.PRE_ACTION,
            purpose=ActionPurpose.ORDINARY_TASK,
            disposition=ControllerDisposition.ALLOW,
            decision_allowed=True,
            reason_codes=("new_action_allowed",),
        )
        first, first_entry = first.append_proposal(**args)
        second, second_entry = second.append_proposal(**args)
        self.assertEqual(first_entry.entry_id, second_entry.entry_id)

    def test_outcome_without_observable_evidence_is_rejected(self) -> None:
        ledger = ActionExecutionLedger("trajectory-evidence")
        ledger, entry = ledger.append_proposal(
            action=ActionSpec("lookup", {"id": "x"}),
            effect_contract=_contract(),
            phase=DecisionPhase.POST_FAILURE,
            purpose=ActionPurpose.ORDINARY_TASK,
            disposition=ControllerDisposition.ALLOW,
            decision_allowed=True,
            reason_codes=("new_action_allowed",),
        )
        ledger = ledger.mark_executed(entry.entry_id)
        with self.assertRaises(ValueError):
            ledger.record_outcome(
                entry.entry_id,
                status=ExecutionStatus.SUCCEEDED,
                evidence=(),
            )

    def test_related_entry_must_refer_to_an_earlier_record(self) -> None:
        entry = LedgerEntry(
            entry_id="entry",
            sequence_index=0,
            action=ActionSpec("lookup", {"id": "x"}),
            effect_contract=_contract(),
            phase=DecisionPhase.POST_FAILURE,
            purpose=ActionPurpose.ORDINARY_TASK,
            status=ExecutionStatus.PROPOSED,
            controller_disposition=ControllerDisposition.REPLAN,
            decision_allowed=False,
            reason_codes=("blocked",),
            related_entry_ids=("future-entry",),
        )
        with self.assertRaises(ValueError):
            ActionExecutionLedger("trajectory-related", entries=(entry,))


if __name__ == "__main__":
    unittest.main()
