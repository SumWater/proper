"""Conservative deterministic selector for unified PROPER v2 development."""

from __future__ import annotations

from typing import Sequence

from .compatibility import evaluate_candidate
from .contracts import (
    CandidateEvaluation,
    Compatibility,
    MemoryPolicyCard,
    ObservableFailure,
    ObservableRecoveryState,
    SelectionDecision,
)


def _validate_candidates(candidates: Sequence[MemoryPolicyCard]) -> None:
    if not candidates:
        raise ValueError("at least one candidate is required")
    ids = [candidate.experience_id for candidate in candidates]
    ranks = [candidate.original_rank for candidate in candidates]
    if len(ids) != len(set(ids)):
        raise ValueError("candidate experience IDs must be unique")
    if len(ranks) != len(set(ranks)) or min(ranks) != 1:
        raise ValueError("candidate ranks must be unique and include Rank-1")


def _decisively_superior(
    alternative: CandidateEvaluation,
    rank1: CandidateEvaluation,
) -> bool:
    if len(alternative.contradictions) < len(rank1.contradictions):
        return True
    if alternative.compatibility.rank > rank1.compatibility.rank:
        return True
    if alternative.precondition_status.rank > rank1.precondition_status.rank:
        return True
    if alternative.repair_target_agreement > rank1.repair_target_agreement:
        return True
    return False


def select_memory(
    target: ObservableFailure | ObservableRecoveryState,
    candidates: Sequence[MemoryPolicyCard],
    *,
    minimum_extraction_confidence: float = 0.75,
) -> SelectionDecision:
    if not 0.0 <= minimum_extraction_confidence <= 1.0:
        raise ValueError("minimum_extraction_confidence must be in [0, 1]")
    _validate_candidates(candidates)

    evaluations = tuple(
        evaluate_candidate(
            target,
            candidate,
            minimum_extraction_confidence=minimum_extraction_confidence,
        )
        for candidate in candidates
    )
    evaluation_by_id = {value.experience_id: value for value in evaluations}
    rank1_card = next(candidate for candidate in candidates if candidate.original_rank == 1)
    rank1 = evaluation_by_id[rank1_card.experience_id]
    best = min(evaluations, key=lambda value: value.sort_key)

    can_replace = (
        best.experience_id != rank1.experience_id
        and best.eligible
        and best.compatibility == Compatibility.COMPATIBLE
        and _decisively_superior(best, rank1)
    )
    if can_replace:
        selected = next(
            candidate for candidate in candidates if candidate.experience_id == best.experience_id
        )
        reason_codes = (
            "replace_rank1_with_decisively_compatible_candidate",
        )
        abstained = False
    else:
        selected = rank1_card
        if (
            best.experience_id == rank1.experience_id
            and rank1.eligible
            and rank1.compatibility == Compatibility.COMPATIBLE
        ):
            reason_codes = ("preserve_rank1_as_best_supported_candidate",)
            abstained = False
        else:
            reason_codes = ("abstain_preserve_rank1_without_decisive_replacement",)
            abstained = True

    ordered_evaluations = tuple(
        sorted(evaluations, key=lambda value: value.original_rank)
    )
    return SelectionDecision(
        rank1_experience_id=rank1.experience_id,
        selected_experience_id=selected.experience_id,
        selected_original_rank=selected.original_rank,
        selection_changed=selected.experience_id != rank1.experience_id,
        abstained=abstained,
        reason_codes=reason_codes,
        minimum_extraction_confidence=minimum_extraction_confidence,
        candidate_evaluations=ordered_evaluations,
        method_version=(
            "proper_v2_1_development"
            if isinstance(target, ObservableRecoveryState)
            else "proper_v2_development"
        ),
    )
