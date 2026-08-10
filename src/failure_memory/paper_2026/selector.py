"""Paper-level conservative selector and prespecified component ablations."""

from __future__ import annotations

from typing import Mapping, Sequence

from failure_memory.proper_v2.compatibility import (
    contradiction_codes,
    precondition_status,
    repair_target_agreement,
    tool_compatibility,
    trigger_evidence_agreement,
)
from failure_memory.proper_v2.contracts import (
    Compatibility,
    MemoryPolicyCard,
    ObservableFailure,
    ObservableRecoveryState,
    RecoveryOperation,
)

from .boundary import candidate_from_mapping, state_from_mapping
from .contracts import (
    PaperCandidateEvaluation,
    PaperSelectionDecision,
    SelectionAction,
    SelectorVariant,
)


ObservableState = ObservableFailure | ObservableRecoveryState


def _validate_candidates(candidates: Sequence[MemoryPolicyCard]) -> None:
    if not candidates:
        raise ValueError("at least one candidate is required")
    ids = [candidate.experience_id for candidate in candidates]
    ranks = [candidate.original_rank for candidate in candidates]
    if len(ids) != len(set(ids)):
        raise ValueError("candidate experience IDs must be unique")
    if sorted(ranks) != list(range(1, len(candidates) + 1)):
        raise ValueError("candidate ranks must be contiguous from Rank-1")


def _evidence_support(
    target: ObservableState,
    candidate: MemoryPolicyCard,
    *,
    trigger_agreement: int,
    repair_agreement: int,
) -> Compatibility:
    operation = candidate.recovery_operation
    if operation == RecoveryOperation.UNKNOWN:
        return Compatibility.INCOMPATIBLE
    if operation == RecoveryOperation.REPAIR_ARGUMENTS:
        supported = trigger_agreement > 0 and repair_agreement > 0
    elif operation == RecoveryOperation.STOP_AND_REPORT:
        supported = bool(set(candidate.stop_conditions) & set(target.evidence_codes))
    else:
        supported = trigger_agreement > 0
    return Compatibility.COMPATIBLE if supported else Compatibility.UNCERTAIN


def _evaluate_candidate(
    target: ObservableState,
    candidate: MemoryPolicyCard,
    *,
    variant: SelectorVariant,
    minimum_extraction_confidence: float,
) -> PaperCandidateEvaluation:
    observed = contradiction_codes(
        target,
        candidate,
        minimum_extraction_confidence=minimum_extraction_confidence,
    )
    active = () if variant == SelectorVariant.NO_CONTRADICTION else observed
    preconditions = precondition_status(target, candidate)
    repair_agreement = repair_target_agreement(target, candidate)
    trigger_agreement = trigger_evidence_agreement(target, candidate)
    tool_agreement = tool_compatibility(target, candidate)
    support = _evidence_support(
        target,
        candidate,
        trigger_agreement=trigger_agreement,
        repair_agreement=repair_agreement,
    )
    sort_key: tuple[int | float | str, ...] = (
        len(active),
        -support.rank,
        -preconditions.rank,
        -repair_agreement,
        -min(trigger_agreement, 3),
        -tool_agreement,
        -candidate.extraction_confidence,
        candidate.original_rank,
        candidate.experience_id,
    )
    return PaperCandidateEvaluation(
        experience_id=candidate.experience_id,
        original_rank=candidate.original_rank,
        observed_contradictions=observed,
        active_contradictions=active,
        eligible=not active,
        precondition_status=preconditions,
        evidence_support=support,
        repair_target_agreement=repair_agreement,
        trigger_evidence_agreement=trigger_agreement,
        tool_compatibility=tool_agreement,
        extraction_confidence=candidate.extraction_confidence,
        sort_key=sort_key,
    )


def _decisively_superior(
    alternative: PaperCandidateEvaluation,
    rank1: PaperCandidateEvaluation,
) -> bool:
    return any(
        (
            len(alternative.active_contradictions) < len(rank1.active_contradictions),
            alternative.evidence_support.rank > rank1.evidence_support.rank,
            alternative.precondition_status.rank > rank1.precondition_status.rank,
            alternative.repair_target_agreement > rank1.repair_target_agreement,
        )
    )


def select_memory(
    target: ObservableState,
    candidates: Sequence[MemoryPolicyCard],
    *,
    variant: SelectorVariant = SelectorVariant.PROPER,
    minimum_extraction_confidence: float = 0.75,
) -> PaperSelectionDecision:
    variant = SelectorVariant(variant)
    if not 0.0 <= minimum_extraction_confidence <= 1.0:
        raise ValueError("minimum_extraction_confidence must be in [0, 1]")
    _validate_candidates(candidates)
    evaluations = tuple(
        _evaluate_candidate(
            target,
            candidate,
            variant=variant,
            minimum_extraction_confidence=minimum_extraction_confidence,
        )
        for candidate in candidates
    )
    by_id = {evaluation.experience_id: evaluation for evaluation in evaluations}
    by_card_id = {candidate.experience_id: candidate for candidate in candidates}
    rank1_card = next(candidate for candidate in candidates if candidate.original_rank == 1)
    rank1 = by_id[rank1_card.experience_id]
    best = min(evaluations, key=lambda value: value.sort_key)

    if variant == SelectorVariant.NO_GATE:
        can_replace = best.experience_id != rank1.experience_id and best.eligible
    else:
        can_replace = (
            best.experience_id != rank1.experience_id
            and best.eligible
            and best.evidence_support == Compatibility.COMPATIBLE
            and _decisively_superior(best, rank1)
        )

    if can_replace:
        selected = by_card_id[best.experience_id]
        action = SelectionAction.SELECT
        reason_codes = (
            (
                "select_best_contradiction_free_candidate_without_conservative_gate"
                if variant == SelectorVariant.NO_GATE
                else "select_decisively_supported_candidate"
            ),
        )
    elif (
        best.experience_id == rank1.experience_id
        and rank1.eligible
        and rank1.evidence_support == Compatibility.COMPATIBLE
    ):
        selected = rank1_card
        action = SelectionAction.KEEP_RANK1
        reason_codes = ("keep_rank1_as_best_supported_candidate",)
    else:
        selected = rank1_card
        action = SelectionAction.ABSTAIN
        reason_codes = ("abstain_and_preserve_rank1_without_authorized_replacement",)

    ordered = tuple(sorted(evaluations, key=lambda value: value.original_rank))
    return PaperSelectionDecision(
        variant=variant,
        action=action,
        rank1_experience_id=rank1.experience_id,
        selected_experience_id=selected.experience_id,
        selected_original_rank=selected.original_rank,
        selection_changed=selected.experience_id != rank1.experience_id,
        abstained=action == SelectionAction.ABSTAIN,
        reason_codes=reason_codes,
        minimum_extraction_confidence=minimum_extraction_confidence,
        candidate_evaluations=ordered,
    )


def select_from_mappings(
    target: Mapping[str, object],
    candidates: Sequence[Mapping[str, object]],
    *,
    variant: SelectorVariant = SelectorVariant.PROPER,
    minimum_extraction_confidence: float = 0.75,
) -> PaperSelectionDecision:
    observable = state_from_mapping(target)
    cards = tuple(candidate_from_mapping(candidate) for candidate in candidates)
    return select_memory(
        observable,
        cards,
        variant=variant,
        minimum_extraction_confidence=minimum_extraction_confidence,
    )
