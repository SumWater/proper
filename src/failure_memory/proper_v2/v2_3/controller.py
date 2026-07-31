"""Scenario-independent execution-aware controller for PROPER v2.3."""

from __future__ import annotations

from dataclasses import replace
from typing import Sequence

from ..contracts import (
    DecisionPhase,
    MemoryPolicyCard,
    ObservableRecoveryState,
    RecoveryOperation,
    RetrySafety,
)
from ..v2_2 import EvidenceStatus, LifecycleStatus, PlanningMode, TriggerStatus
from .contracts import (
    ActionEffectClass,
    ActionEffectContract,
    ActionPurpose,
    ActionSpec,
    BudgetPolicy,
    ControllerDecision,
    ControllerDisposition,
    ControllerState,
    ExecutionStatus,
)
from .ledger import ActionExecutionLedger, LedgerEntry


def initial_controller_state(
    *,
    phase: DecisionPhase,
    selected_memory_experience_id: str,
    memory_operation: RecoveryOperation,
    memory_action: ActionSpec | None,
    budget_policy: BudgetPolicy,
) -> ControllerState:
    return ControllerState(
        phase=phase,
        selected_memory_experience_id=selected_memory_experience_id,
        memory_operation=memory_operation,
        memory_action_identity=memory_action.identity if memory_action else None,
        lifecycle_status=LifecycleStatus.ACTIVE,
        planning_mode=PlanningMode.MEMORY_GUIDED,
        budgets=budget_policy.initial_state(),
    )


def controller_state_from_selection(
    *,
    observable_state: ObservableRecoveryState,
    selected_memory: MemoryPolicyCard,
    budget_policy: BudgetPolicy,
) -> ControllerState:
    """Start the same controller interface from either observable phase."""

    memory_action = (
        ActionSpec(
            selected_memory.proposed_action.tool_name,
            selected_memory.proposed_action.argument_template,
        )
        if selected_memory.proposed_action is not None
        else None
    )
    return initial_controller_state(
        phase=observable_state.phase,
        selected_memory_experience_id=selected_memory.experience_id,
        memory_operation=selected_memory.recovery_operation,
        memory_action=memory_action,
        budget_policy=budget_policy,
    )


def _stopped(
    state: ControllerState,
    reason: str,
    *,
    failed: bool = False,
) -> ControllerState:
    return replace(
        state,
        lifecycle_status=(
            LifecycleStatus.FAILED if failed else LifecycleStatus.STOPPED
        ),
        planning_mode=PlanningMode.STOPPED,
        transition_index=state.transition_index + 1,
        verification_required_for_entry_id=None,
        stop_reason=reason,
    )


def _replan_state(state: ControllerState, reason: str) -> ControllerState:
    if state.budgets.remaining_replans == 0:
        return _stopped(state, f"{reason}:replan_budget_exhausted")
    return replace(
        state,
        budgets=replace(
            state.budgets,
            remaining_replans=state.budgets.remaining_replans - 1,
        ),
        transition_index=state.transition_index + 1,
    )


def _append_review(
    ledger: ActionExecutionLedger,
    *,
    state: ControllerState,
    action: ActionSpec,
    effect_contract: ActionEffectContract,
    purpose: ActionPurpose,
    disposition: ControllerDisposition,
    allowed: bool,
    reason: str,
    related: Sequence[LedgerEntry] = (),
) -> tuple[ActionExecutionLedger, ControllerDecision]:
    updated, entry = ledger.append_proposal(
        action=action,
        effect_contract=effect_contract,
        phase=state.phase,
        purpose=purpose,
        disposition=disposition,
        decision_allowed=allowed,
        reason_codes=(reason,),
        related_entry_ids=tuple(item.entry_id for item in related),
    )
    return updated, ControllerDecision(
        disposition=disposition,
        decision_allowed=allowed,
        reason_code=reason,
        ledger_entry_id=entry.entry_id,
        state=state,
    )


def _contract_update_is_observable_and_safe(
    previous: ActionEffectContract,
    current: ActionEffectContract,
) -> bool:
    if previous.effect_class != current.effect_class:
        return False
    if previous.classification_evidence != current.classification_evidence:
        return False
    if previous.verification_supported != current.verification_supported:
        return False
    if previous.verification_evidence != current.verification_evidence:
        return False
    if not set(previous.retry_safety_evidence).issubset(
        set(current.retry_safety_evidence)
    ):
        return False
    if previous.retry_safety == current.retry_safety:
        return True
    return previous.retry_safety == RetrySafety.UNKNOWN


def review_action_proposal(
    *,
    state: ControllerState,
    ledger: ActionExecutionLedger,
    action: ActionSpec,
    effect_contract: ActionEffectContract,
    purpose: ActionPurpose,
    verifies_entry_id: str | None = None,
) -> tuple[ActionExecutionLedger, ControllerDecision]:
    """Review and ledger one proposed action before any tool execution."""

    if state.lifecycle_status in {LifecycleStatus.FAILED, LifecycleStatus.STOPPED}:
        reason = state.stop_reason or "terminal_controller_state"
        return _append_review(
            ledger,
            state=state,
            action=action,
            effect_contract=effect_contract,
            purpose=purpose,
            disposition=ControllerDisposition.STOP,
            allowed=False,
            reason=reason,
        )

    if (
        state.lifecycle_status == LifecycleStatus.ACTIVE
        and state.memory_operation == RecoveryOperation.STOP_AND_REPORT
    ):
        stopped = _stopped(state, "active_stop_policy_tool_call_blocked")
        return _append_review(
            ledger,
            state=stopped,
            action=action,
            effect_contract=effect_contract,
            purpose=purpose,
            disposition=ControllerDisposition.STOP,
            allowed=False,
            reason="active_stop_policy_tool_call_blocked",
        )

    history = ledger.matching_entries(action.identity)
    inconsistent_contracts = tuple(
        item
        for item in history
        if not _contract_update_is_observable_and_safe(
            item.effect_contract,
            effect_contract,
        )
    )
    if inconsistent_contracts:
        stopped = _stopped(state, "action_effect_contract_changed", failed=True)
        return _append_review(
            ledger,
            state=stopped,
            action=action,
            effect_contract=effect_contract,
            purpose=purpose,
            disposition=ControllerDisposition.STOP,
            allowed=False,
            reason="action_effect_contract_changed",
            related=inconsistent_contracts,
        )

    if effect_contract.effect_class == ActionEffectClass.UNKNOWN_EFFECT:
        stopped = _stopped(state, "unknown_action_effect_fails_closed")
        return _append_review(
            ledger,
            state=stopped,
            action=action,
            effect_contract=effect_contract,
            purpose=purpose,
            disposition=ControllerDisposition.STOP,
            allowed=False,
            reason="unknown_action_effect_fails_closed",
        )

    if state.verification_required_for_entry_id is not None:
        verification_valid = (
            purpose == ActionPurpose.VERIFICATION
            and verifies_entry_id == state.verification_required_for_entry_id
            and effect_contract.effect_class == ActionEffectClass.READ_ONLY
        )
        if not verification_valid:
            return _append_review(
                ledger,
                state=state,
                action=action,
                effect_contract=effect_contract,
                purpose=purpose,
                disposition=ControllerDisposition.VERIFY,
                allowed=False,
                reason="required_verification_must_precede_other_actions",
            )
        successful_verifications = tuple(
            item for item in history if item.status == ExecutionStatus.SUCCEEDED
        )
        if successful_verifications:
            replanned = _replan_state(state, "successful_verification_repeat_blocked")
            disposition = (
                ControllerDisposition.STOP
                if replanned.lifecycle_status == LifecycleStatus.STOPPED
                else ControllerDisposition.REPLAN
            )
            return _append_review(
                ledger,
                state=replanned,
                action=action,
                effect_contract=effect_contract,
                purpose=purpose,
                disposition=disposition,
                allowed=False,
                reason=(
                    replanned.stop_reason
                    or "successful_verification_repeat_blocked"
                ),
                related=successful_verifications,
            )
        unresolved_verifications = tuple(
            item
            for item in history
            if item.status
            in {ExecutionStatus.EXECUTED, ExecutionStatus.OUTCOME_UNKNOWN}
        )
        if unresolved_verifications:
            stopped = _stopped(
                state,
                "verification_action_outcome_unresolved",
                failed=True,
            )
            return _append_review(
                ledger,
                state=stopped,
                action=action,
                effect_contract=effect_contract,
                purpose=purpose,
                disposition=ControllerDisposition.STOP,
                allowed=False,
                reason="verification_action_outcome_unresolved",
                related=unresolved_verifications,
            )
        failed_verifications = tuple(
            item for item in history if item.status == ExecutionStatus.FAILED
        )
        retrying_verification = bool(failed_verifications)
        if retrying_verification and (
            effect_contract.retry_safety != RetrySafety.SAFE
            or state.budgets.remaining_retries == 0
        ):
            stopped = _stopped(state, "verification_retry_not_safe", failed=True)
            return _append_review(
                ledger,
                state=stopped,
                action=action,
                effect_contract=effect_contract,
                purpose=purpose,
                disposition=ControllerDisposition.STOP,
                allowed=False,
                reason="verification_retry_not_safe",
                related=failed_verifications,
            )
        if state.budgets.remaining_verifications == 0:
            stopped = _stopped(state, "verification_budget_exhausted", failed=True)
            return _append_review(
                ledger,
                state=stopped,
                action=action,
                effect_contract=effect_contract,
                purpose=purpose,
                disposition=ControllerDisposition.STOP,
                allowed=False,
                reason="verification_budget_exhausted",
            )
        verifying = replace(
            state,
            budgets=replace(
                state.budgets,
                remaining_verifications=state.budgets.remaining_verifications - 1,
                remaining_retries=(
                    state.budgets.remaining_retries - 1
                    if retrying_verification
                    else state.budgets.remaining_retries
                ),
            ),
            transition_index=state.transition_index + 1,
        )
        related = (ledger.entry(verifies_entry_id),) + failed_verifications
        return _append_review(
            ledger,
            state=verifying,
            action=action,
            effect_contract=effect_contract,
            purpose=purpose,
            disposition=ControllerDisposition.VERIFY,
            allowed=True,
            reason="bounded_read_only_verification_allowed",
            related=related,
        )

    successful = tuple(
        item for item in history if item.status == ExecutionStatus.SUCCEEDED
    )
    if successful:
        replanned = _replan_state(state, "successful_action_repeat_blocked")
        disposition = (
            ControllerDisposition.STOP
            if replanned.lifecycle_status == LifecycleStatus.STOPPED
            else ControllerDisposition.REPLAN
        )
        reason = (
            replanned.stop_reason
            if disposition == ControllerDisposition.STOP
            else "successful_action_repeat_blocked"
        )
        return _append_review(
            ledger,
            state=replanned,
            action=action,
            effect_contract=effect_contract,
            purpose=purpose,
            disposition=disposition,
            allowed=False,
            reason=str(reason),
            related=successful,
        )

    unresolved = tuple(
        item
        for item in history
        if item.status in {ExecutionStatus.EXECUTED, ExecutionStatus.OUTCOME_UNKNOWN}
    )
    if unresolved:
        latest = unresolved[-1]
        if (
            latest.effect_contract.verification_supported
            and state.budgets.remaining_verifications > 0
        ):
            verifying = replace(
                state,
                verification_required_for_entry_id=latest.entry_id,
                transition_index=state.transition_index + 1,
            )
            return _append_review(
                ledger,
                state=verifying,
                action=action,
                effect_contract=effect_contract,
                purpose=purpose,
                disposition=ControllerDisposition.VERIFY,
                allowed=False,
                reason="unknown_outcome_requires_verification",
                related=unresolved,
            )
        stopped = _stopped(state, "unknown_outcome_without_safe_verification", failed=True)
        return _append_review(
            ledger,
            state=stopped,
            action=action,
            effect_contract=effect_contract,
            purpose=purpose,
            disposition=ControllerDisposition.STOP,
            allowed=False,
            reason="unknown_outcome_without_safe_verification",
            related=unresolved,
        )

    failures = tuple(item for item in history if item.status == ExecutionStatus.FAILED)
    if failures:
        if (
            effect_contract.retry_safety == RetrySafety.SAFE
            and state.budgets.remaining_retries > 0
        ):
            retrying = replace(
                state,
                budgets=replace(
                    state.budgets,
                    remaining_retries=state.budgets.remaining_retries - 1,
                ),
                transition_index=state.transition_index + 1,
            )
            return _append_review(
                ledger,
                state=retrying,
                action=action,
                effect_contract=effect_contract,
                purpose=purpose,
                disposition=ControllerDisposition.ALLOW,
                allowed=True,
                reason="publicly_retry_safe_failure_retry_allowed",
                related=failures,
            )
        replanned = _replan_state(state, "unsafe_or_unproven_retry_blocked")
        disposition = (
            ControllerDisposition.STOP
            if replanned.lifecycle_status == LifecycleStatus.STOPPED
            else ControllerDisposition.REPLAN
        )
        reason = replanned.stop_reason or "unsafe_or_unproven_retry_blocked"
        return _append_review(
            ledger,
            state=replanned,
            action=action,
            effect_contract=effect_contract,
            purpose=purpose,
            disposition=disposition,
            allowed=False,
            reason=reason,
            related=failures,
        )

    pending = tuple(item for item in history if item.status == ExecutionStatus.PROPOSED)
    if pending:
        replanned = _replan_state(state, "duplicate_pending_proposal_blocked")
        disposition = (
            ControllerDisposition.STOP
            if replanned.lifecycle_status == LifecycleStatus.STOPPED
            else ControllerDisposition.REPLAN
        )
        reason = replanned.stop_reason or "duplicate_pending_proposal_blocked"
        return _append_review(
            ledger,
            state=replanned,
            action=action,
            effect_contract=effect_contract,
            purpose=purpose,
            disposition=disposition,
            allowed=False,
            reason=reason,
            related=pending,
        )

    return _append_review(
        ledger,
        state=state,
        action=action,
        effect_contract=effect_contract,
        purpose=purpose,
        disposition=ControllerDisposition.ALLOW,
        allowed=True,
        reason="new_action_allowed",
    )


def observe_execution(
    *,
    state: ControllerState,
    ledger: ActionExecutionLedger,
    entry_id: str,
    trigger_status: TriggerStatus = TriggerStatus.UNKNOWN,
    success_evidence_status: EvidenceStatus = EvidenceStatus.UNKNOWN,
) -> ControllerState:
    """Advance lifecycle from one already-recorded observable execution outcome."""

    entry = ledger.entry(entry_id)
    if entry.status not in {
        ExecutionStatus.SUCCEEDED,
        ExecutionStatus.FAILED,
        ExecutionStatus.OUTCOME_UNKNOWN,
    }:
        raise ValueError("execution observation requires a recorded outcome")
    is_memory_action = (
        state.memory_action_identity is not None
        and entry.normalized_identity == state.memory_action_identity
        and entry.purpose == ActionPurpose.RECOVERY
    )

    if entry.status == ExecutionStatus.OUTCOME_UNKNOWN:
        if entry.effect_contract.verification_supported:
            return replace(
                state,
                verification_required_for_entry_id=entry.entry_id,
                transition_index=state.transition_index + 1,
            )
        return _stopped(state, "outcome_unknown_without_verification_path", failed=True)

    if not is_memory_action:
        return replace(
            state,
            verification_required_for_entry_id=None,
            transition_index=state.transition_index + 1,
        )

    if entry.status == ExecutionStatus.FAILED:
        return replace(
            state,
            verification_required_for_entry_id=None,
            transition_index=state.transition_index + 1,
        )

    if success_evidence_status == EvidenceStatus.VIOLATED:
        return _stopped(state, "runtime_success_evidence_violated", failed=True)

    if (
        trigger_status == TriggerStatus.HOLDS
        and success_evidence_status == EvidenceStatus.SATISFIED
    ):
        return _stopped(
            state,
            "success_evidence_conflicts_with_active_trigger",
            failed=True,
        )
    if trigger_status == TriggerStatus.CLEARED or (
        success_evidence_status == EvidenceStatus.SATISFIED
        and trigger_status != TriggerStatus.HOLDS
    ):
        return replace(
            state,
            lifecycle_status=LifecycleStatus.CONSUMED,
            planning_mode=PlanningMode.ORDINARY_TASK_PLANNING,
            transition_index=state.transition_index + 1,
            verification_required_for_entry_id=None,
            stop_reason=None,
        )
    if entry.effect_contract.verification_supported:
        return replace(
            state,
            verification_required_for_entry_id=entry.entry_id,
            transition_index=state.transition_index + 1,
        )
    return _stopped(state, "successful_recovery_lacks_success_evidence", failed=True)


def resolve_verification(
    *,
    state: ControllerState,
    ledger: ActionExecutionLedger,
    verified_entry_id: str,
    verified_status: ExecutionStatus,
    trigger_status: TriggerStatus = TriggerStatus.UNKNOWN,
    success_evidence_status: EvidenceStatus = EvidenceStatus.UNKNOWN,
) -> ControllerState:
    if state.verification_required_for_entry_id != verified_entry_id:
        raise ValueError("verification does not match the required ledger entry")
    if verified_status not in {ExecutionStatus.SUCCEEDED, ExecutionStatus.FAILED}:
        raise ValueError("verification must resolve to succeeded or failed")
    verified_entry = ledger.entry(verified_entry_id)
    if verified_entry.status != verified_status:
        raise ValueError("verified status must match the resolved ledger outcome")
    is_memory_action = (
        state.memory_action_identity is not None
        and verified_entry.normalized_identity == state.memory_action_identity
        and verified_entry.purpose == ActionPurpose.RECOVERY
    )
    if not is_memory_action:
        return replace(
            state,
            verification_required_for_entry_id=None,
            transition_index=state.transition_index + 1,
        )
    if verified_status == ExecutionStatus.SUCCEEDED and is_memory_action:
        if (
            trigger_status == TriggerStatus.HOLDS
            or success_evidence_status == EvidenceStatus.VIOLATED
        ):
            return _stopped(
                state,
                "verified_success_conflicts_with_active_trigger",
                failed=True,
            )
        if (
            trigger_status == TriggerStatus.CLEARED
            or success_evidence_status == EvidenceStatus.SATISFIED
        ):
            return replace(
                state,
                lifecycle_status=LifecycleStatus.CONSUMED,
                planning_mode=PlanningMode.ORDINARY_TASK_PLANNING,
                verification_required_for_entry_id=None,
                transition_index=state.transition_index + 1,
            )
    if verified_status == ExecutionStatus.FAILED:
        return replace(
            state,
            verification_required_for_entry_id=None,
            transition_index=state.transition_index + 1,
        )
    return _stopped(state, "verification_did_not_establish_safe_progress", failed=True)


def review_invalid_decision(state: ControllerState) -> ControllerDecision:
    if state.lifecycle_status in {LifecycleStatus.FAILED, LifecycleStatus.STOPPED}:
        return ControllerDecision(
            disposition=ControllerDisposition.STOP,
            decision_allowed=False,
            reason_code=state.stop_reason or "terminal_controller_state",
            ledger_entry_id=None,
            state=state,
        )
    if state.budgets.remaining_invalid_decisions == 0:
        stopped = _stopped(state, "invalid_decision_budget_exhausted")
        return ControllerDecision(
            disposition=ControllerDisposition.STOP,
            decision_allowed=False,
            reason_code="invalid_decision_budget_exhausted",
            ledger_entry_id=None,
            state=stopped,
        )
    replanning = replace(
        state,
        budgets=replace(
            state.budgets,
            remaining_invalid_decisions=(
                state.budgets.remaining_invalid_decisions - 1
            ),
        ),
        transition_index=state.transition_index + 1,
    )
    return ControllerDecision(
        disposition=ControllerDisposition.REPLAN,
        decision_allowed=False,
        reason_code="invalid_decision_replan_required",
        ledger_entry_id=None,
        state=replanning,
    )


def stop_for_task_completion(state: ControllerState) -> ControllerState:
    return _stopped(state, "task_complete")


def stop_for_agent_decision(
    state: ControllerState,
    *,
    reason_code: str,
) -> ControllerState:
    if not reason_code:
        raise ValueError("agent stop reason_code cannot be empty")
    return _stopped(state, f"agent_stop:{reason_code}")
