"""Scenario-independent compatibility evaluation for PROPER v2."""

from __future__ import annotations

from .contracts import (
    CandidateEvaluation,
    Compatibility,
    ContinuationPolicy,
    DecisionPhase,
    MemoryPolicyCard,
    ObservableFailure,
    ObservableRecoveryState,
    RecoveryOperation,
    RetrySafety,
    TruthStatus,
)

ObservableState = ObservableFailure | ObservableRecoveryState


def precondition_status(
    target: ObservableState, candidate: MemoryPolicyCard
) -> TruthStatus:
    required = set(candidate.required_preconditions)
    if not required:
        return TruthStatus.SATISFIED
    if required & set(target.violated_facts):
        return TruthStatus.VIOLATED
    if required.issubset(set(target.satisfied_facts)):
        return TruthStatus.SATISFIED
    return TruthStatus.UNKNOWN


def repair_target_agreement(
    target: ObservableState, candidate: MemoryPolicyCard
) -> int:
    if candidate.recovery_operation != RecoveryOperation.REPAIR_ARGUMENTS:
        return 0
    expected = set(target.missing_fields)
    proposed = set(candidate.repair_targets)
    if not expected or not proposed:
        return 0
    if expected == proposed:
        return 2
    return int(bool(expected & proposed))


def trigger_evidence_agreement(
    target: ObservableState, candidate: MemoryPolicyCard
) -> int:
    return len(set(target.evidence_codes) & set(candidate.trigger_evidence))


def tool_compatibility(
    target: ObservableState, candidate: MemoryPolicyCard
) -> int:
    proposed_tool = candidate.proposed_action.tool_name if candidate.proposed_action else None
    if proposed_tool == target.tool_name or candidate.source_tool == target.tool_name:
        return 2
    if proposed_tool is not None and proposed_tool in target.available_tools:
        return 1
    return 0


def contradiction_codes(
    target: ObservableState,
    candidate: MemoryPolicyCard,
    *,
    minimum_extraction_confidence: float,
) -> tuple[str, ...]:
    found: set[str] = set()
    status = precondition_status(target, candidate)
    operation = candidate.recovery_operation
    proposed_tool = candidate.proposed_action.tool_name if candidate.proposed_action else None
    phase = (
        target.phase
        if isinstance(target, ObservableRecoveryState)
        else DecisionPhase.POST_FAILURE
    )

    if candidate.extraction_confidence < minimum_extraction_confidence:
        found.add("extraction_confidence_below_minimum")
    if operation == RecoveryOperation.UNKNOWN:
        found.add("unknown_recovery_operation")
    if phase == DecisionPhase.PRE_ACTION:
        if operation == RecoveryOperation.RETRY_SAME_ACTION:
            found.add("retry_requires_post_failure")
        if operation == RecoveryOperation.REPAIR_ARGUMENTS:
            found.add("repair_requires_post_failure")
    if status == TruthStatus.VIOLATED:
        found.add("required_precondition_violated")
    if operation == RecoveryOperation.RETRY_SAME_ACTION:
        if target.retry_safety.status == RetrySafety.UNSAFE:
            found.add("retry_publicly_unsafe")
        elif target.retry_safety.status == RetrySafety.UNKNOWN:
            found.add("retry_safety_unknown")
        if proposed_tool is not None and proposed_tool != target.tool_name:
            found.add("retry_changes_tool")
    if proposed_tool is not None and proposed_tool not in target.available_tools:
        found.add("proposed_tool_unavailable")
    if operation == RecoveryOperation.SWITCH_TOOL:
        if proposed_tool is None:
            found.add("switch_tool_missing_action")
        elif proposed_tool == target.tool_name:
            found.add("switch_tool_does_not_switch")
    if operation == RecoveryOperation.REPAIR_ARGUMENTS:
        repair_targets = set(candidate.repair_targets)
        if repair_targets and not repair_targets.issubset(set(target.public_schema_fields)):
            found.add("repair_target_absent_from_public_schema")
        if target.missing_fields and repair_target_agreement(target, candidate) == 0:
            found.add("repair_target_mismatch")
    if (
        operation == RecoveryOperation.STOP_AND_REPORT
        and candidate.continuation_policy != ContinuationPolicy.TERMINATE
    ):
        found.add("stop_policy_does_not_terminate")
    return tuple(sorted(found))


def evaluate_candidate(
    target: ObservableState,
    candidate: MemoryPolicyCard,
    *,
    minimum_extraction_confidence: float,
) -> CandidateEvaluation:
    preconditions = precondition_status(target, candidate)
    contradictions = contradiction_codes(
        target,
        candidate,
        minimum_extraction_confidence=minimum_extraction_confidence,
    )
    repair_agreement = repair_target_agreement(target, candidate)
    trigger_agreement = trigger_evidence_agreement(target, candidate)
    tool_agreement = tool_compatibility(target, candidate)
    eligible = not contradictions

    operation_supported = False
    if candidate.recovery_operation == RecoveryOperation.RETRY_SAME_ACTION:
        operation_supported = (
            target.retry_safety.status == RetrySafety.SAFE and trigger_agreement > 0
        )
    elif candidate.recovery_operation == RecoveryOperation.REPAIR_ARGUMENTS:
        operation_supported = repair_agreement > 0 and trigger_agreement > 0
    elif candidate.recovery_operation == RecoveryOperation.STOP_AND_REPORT:
        operation_supported = bool(
            set(candidate.stop_conditions) & set(target.evidence_codes)
        )
    elif candidate.recovery_operation != RecoveryOperation.UNKNOWN:
        operation_supported = trigger_agreement > 0

    if not eligible:
        compatibility = Compatibility.INCOMPATIBLE
    elif preconditions == TruthStatus.UNKNOWN or not operation_supported:
        compatibility = Compatibility.UNCERTAIN
    else:
        compatibility = Compatibility.COMPATIBLE

    sort_key: tuple[int | float | str, ...] = (
        len(contradictions),
        -compatibility.rank,
        -preconditions.rank,
        -repair_agreement,
        -min(trigger_agreement, 3),
        -tool_agreement,
        -candidate.extraction_confidence,
        candidate.original_rank,
        candidate.experience_id,
    )
    return CandidateEvaluation(
        experience_id=candidate.experience_id,
        original_rank=candidate.original_rank,
        eligible=eligible,
        contradictions=contradictions,
        precondition_status=preconditions,
        compatibility=compatibility,
        repair_target_agreement=repair_agreement,
        trigger_evidence_agreement=trigger_agreement,
        tool_compatibility=tool_agreement,
        extraction_confidence=candidate.extraction_confidence,
        sort_key=sort_key,
    )
