"""Dependency-light scripted multi-step traces for PROPER v2.3.

These traces contain no model behavior and no ToolSandbox scenario branch.
They exercise public action-effect contracts, the complete ledger, lifecycle
handoff, and controller dispositions.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from failure_memory.proper_v2 import DecisionPhase, RecoveryOperation, RetrySafety  # noqa: E402
from failure_memory.proper_v2.v2_2 import EvidenceStatus, TriggerStatus  # noqa: E402
from failure_memory.proper_v2.v2_3 import (  # noqa: E402
    ActionEffectClass,
    ActionEffectContract,
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
    review_action_proposal,
)


def read_only_contract(*, verification_supported: bool = False) -> ActionEffectContract:
    return ActionEffectContract(
        effect_class=ActionEffectClass.READ_ONLY,
        classification_evidence=("tool_schema:read_only",),
        retry_safety=RetrySafety.SAFE,
        retry_safety_evidence=("public_contract:no_side_effect_on_retry",),
        verification_supported=verification_supported,
        verification_evidence=(
            ("tool_schema:read_after_write_verifier",)
            if verification_supported
            else ()
        ),
    )


def state_setting_contract() -> ActionEffectContract:
    return ActionEffectContract(
        effect_class=ActionEffectClass.IDEMPOTENT_STATE_SETTING,
        classification_evidence=("tool_schema:set_absolute_state",),
        retry_safety=RetrySafety.SAFE,
        retry_safety_evidence=("public_contract:same_value_is_idempotent",),
        verification_supported=True,
        verification_evidence=("tool_schema:public_state_query",),
    )


def side_effect_contract() -> ActionEffectContract:
    return ActionEffectContract(
        effect_class=ActionEffectClass.NON_IDEMPOTENT_SIDE_EFFECT,
        classification_evidence=("tool_schema:sends_external_message",),
        retry_safety=RetrySafety.UNSAFE,
        retry_safety_evidence=("public_contract:duplicate_delivery_possible",),
        verification_supported=True,
        verification_evidence=("tool_schema:delivery_receipt_query",),
    )


def _record(
    ledger: ActionExecutionLedger,
    entry_id: str,
    status: ExecutionStatus,
    *,
    step: int,
    code: str,
) -> ActionExecutionLedger:
    executed = ledger.mark_executed(
        entry_id,
        evidence=(
            EvidenceRecord(
                source=EvidenceSource.CONTROLLER,
                code="controller_allowed_execution",
                observed_at_step=step,
            ),
        ),
    )
    return executed.record_outcome(
        entry_id,
        status=status,
        evidence=(
            EvidenceRecord(
                source=EvidenceSource.TOOL_RESULT,
                code=code,
                observed_at_step=step,
            ),
        ),
    )


def _consumed_start(trajectory_id: str) -> tuple[Any, ActionExecutionLedger, ActionSpec]:
    recovery = ActionSpec("set_connectivity", {"enabled": True})
    state = initial_controller_state(
        phase=DecisionPhase.POST_FAILURE,
        selected_memory_experience_id="development-memory::connectivity",
        memory_operation=RecoveryOperation.INVOKE_PREREQUISITE,
        memory_action=recovery,
        budget_policy=BudgetPolicy(),
    )
    ledger = ActionExecutionLedger(trajectory_id)
    ledger, review = review_action_proposal(
        state=state,
        ledger=ledger,
        action=recovery,
        effect_contract=state_setting_contract(),
        purpose=ActionPurpose.RECOVERY,
    )
    if not review.decision_allowed or review.ledger_entry_id is None:
        raise AssertionError("scripted recovery must be allowed")
    ledger = _record(
        ledger,
        review.ledger_entry_id,
        ExecutionStatus.SUCCEEDED,
        step=1,
        code="public_state:connectivity_enabled",
    )
    state = observe_execution(
        state=review.state,
        ledger=ledger,
        entry_id=review.ledger_entry_id,
        trigger_status=TriggerStatus.CLEARED,
        success_evidence_status=EvidenceStatus.SATISFIED,
    )
    return state, ledger, recovery


def trace_pre_action_safe_stop() -> dict[str, Any]:
    state = initial_controller_state(
        phase=DecisionPhase.PRE_ACTION,
        selected_memory_experience_id="development-memory::ask-or-stop",
        memory_operation=RecoveryOperation.STOP_AND_REPORT,
        memory_action=None,
        budget_policy=BudgetPolicy(),
    )
    ledger, review = review_action_proposal(
        state=state,
        ledger=ActionExecutionLedger("trace-pre-action-safe-stop"),
        action=ActionSpec("destructive_action", {"target": "unresolved"}),
        effect_contract=side_effect_contract(),
        purpose=ActionPurpose.ORDINARY_TASK,
    )
    return {
        "trace_id": "pre_action_safe_stop",
        "passed": (
            review.disposition == ControllerDisposition.STOP
            and not review.decision_allowed
            and len(ledger.entries) == 1
        ),
        "decision": review.to_mapping(),
        "ledger": ledger.to_mapping(),
    }


def trace_consumption_and_handoff() -> dict[str, Any]:
    state, ledger, recovery = _consumed_start("trace-consumption-handoff")
    ordinary = ActionSpec("lookup_public_state", {"scope": "next_step"})
    ledger, ordinary_review = review_action_proposal(
        state=state,
        ledger=ledger,
        action=ordinary,
        effect_contract=read_only_contract(),
        purpose=ActionPurpose.ORDINARY_TASK,
    )
    ledger, repeat_review = review_action_proposal(
        state=ordinary_review.state,
        ledger=ledger,
        action=recovery,
        effect_contract=state_setting_contract(),
        purpose=ActionPurpose.RECOVERY,
    )
    return {
        "trace_id": "consumption_and_handoff",
        "passed": (
            state.lifecycle_status.value == "consumed"
            and ordinary_review.disposition == ControllerDisposition.ALLOW
            and repeat_review.disposition == ControllerDisposition.REPLAN
            and not repeat_review.decision_allowed
        ),
        "ordinary_decision": ordinary_review.to_mapping(),
        "repeat_decision": repeat_review.to_mapping(),
        "ledger": ledger.to_mapping(),
    }


def trace_duplicate_message_blocked() -> dict[str, Any]:
    state, ledger, _ = _consumed_start("trace-duplicate-message")
    message = ActionSpec(
        "send_message",
        {"recipient": "contact-1", "text": "Status update"},
    )
    ledger, first = review_action_proposal(
        state=state,
        ledger=ledger,
        action=message,
        effect_contract=side_effect_contract(),
        purpose=ActionPurpose.ORDINARY_TASK,
    )
    if first.ledger_entry_id is None:
        raise AssertionError("first message proposal missing ledger identity")
    ledger = _record(
        ledger,
        first.ledger_entry_id,
        ExecutionStatus.SUCCEEDED,
        step=2,
        code="tool_result:message_sent",
    )
    state = observe_execution(
        state=first.state,
        ledger=ledger,
        entry_id=first.ledger_entry_id,
    )
    ledger, repeated = review_action_proposal(
        state=state,
        ledger=ledger,
        action=message,
        effect_contract=side_effect_contract(),
        purpose=ActionPurpose.ORDINARY_TASK,
    )
    executed_messages = [
        entry
        for entry in ledger.entries
        if entry.normalized_identity == message.identity
        and entry.status
        in {
            ExecutionStatus.EXECUTED,
            ExecutionStatus.SUCCEEDED,
            ExecutionStatus.FAILED,
            ExecutionStatus.OUTCOME_UNKNOWN,
        }
    ]
    return {
        "trace_id": "duplicate_message_blocked",
        "passed": (
            repeated.disposition == ControllerDisposition.REPLAN
            and not repeated.decision_allowed
            and len(executed_messages) == 1
        ),
        "repeat_decision": repeated.to_mapping(),
        "executed_message_count": len(executed_messages),
        "ledger": ledger.to_mapping(),
    }


def trace_unknown_side_effect_requires_verification() -> dict[str, Any]:
    state, ledger, _ = _consumed_start("trace-unknown-side-effect")
    message = ActionSpec(
        "send_message",
        {"recipient": "contact-2", "text": "One delivery only"},
    )
    ledger, first = review_action_proposal(
        state=state,
        ledger=ledger,
        action=message,
        effect_contract=side_effect_contract(),
        purpose=ActionPurpose.ORDINARY_TASK,
    )
    if first.ledger_entry_id is None:
        raise AssertionError("message proposal missing ledger identity")
    ledger = _record(
        ledger,
        first.ledger_entry_id,
        ExecutionStatus.OUTCOME_UNKNOWN,
        step=2,
        code="transport:response_lost",
    )
    state = observe_execution(
        state=first.state,
        ledger=ledger,
        entry_id=first.ledger_entry_id,
    )
    verifier = ActionSpec("get_delivery_receipt", {"recipient": "contact-2"})
    ledger, verification = review_action_proposal(
        state=state,
        ledger=ledger,
        action=verifier,
        effect_contract=read_only_contract(),
        purpose=ActionPurpose.VERIFICATION,
        verifies_entry_id=first.ledger_entry_id,
    )
    return {
        "trace_id": "unknown_side_effect_requires_verification",
        "passed": (
            verification.disposition == ControllerDisposition.VERIFY
            and verification.decision_allowed
            and verification.state.budgets.remaining_verifications == 1
        ),
        "verification_decision": verification.to_mapping(),
        "ledger": ledger.to_mapping(),
    }


def trace_idempotent_success_repeat_blocked() -> dict[str, Any]:
    state, ledger, recovery = _consumed_start("trace-idempotent-repeat")
    ledger, repeated = review_action_proposal(
        state=state,
        ledger=ledger,
        action=recovery,
        effect_contract=state_setting_contract(),
        purpose=ActionPurpose.ORDINARY_TASK,
    )
    return {
        "trace_id": "idempotent_success_repeat_blocked",
        "passed": (
            repeated.disposition == ControllerDisposition.REPLAN
            and not repeated.decision_allowed
        ),
        "repeat_decision": repeated.to_mapping(),
        "ledger": ledger.to_mapping(),
    }


def run_scripted_traces() -> dict[str, Any]:
    traces = [
        trace_pre_action_safe_stop(),
        trace_consumption_and_handoff(),
        trace_duplicate_message_blocked(),
        trace_unknown_side_effect_requires_verification(),
        trace_idempotent_success_repeat_blocked(),
    ]
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_3_scripted_multi_step_validation",
        "model_loaded": False,
        "model_outputs_read": False,
        "gpu_used": False,
        "scenario_specific_controller_branch_count": 0,
        "trace_count": len(traces),
        "passed_trace_count": sum(bool(item["passed"]) for item in traces),
        "passed": all(bool(item["passed"]) for item in traces),
        "traces": traces,
    }


def main() -> int:
    result = run_scripted_traces()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
