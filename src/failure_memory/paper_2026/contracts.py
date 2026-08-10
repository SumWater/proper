"""Typed, auditable contracts for the paper-level PROPER selector."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from failure_memory.proper_v2.contracts import Compatibility, TruthStatus


class SelectorVariant(str, Enum):
    PROPER = "proper"
    NO_GATE = "proper_no_gate"
    NO_CONTRADICTION = "proper_no_contradiction"


class SelectionAction(str, Enum):
    KEEP_RANK1 = "keep_rank1"
    SELECT = "select"
    ABSTAIN = "abstain"


@dataclass(frozen=True)
class PaperCandidateEvaluation:
    experience_id: str
    original_rank: int
    observed_contradictions: tuple[str, ...]
    active_contradictions: tuple[str, ...]
    eligible: bool
    precondition_status: TruthStatus
    evidence_support: Compatibility
    repair_target_agreement: int
    trigger_evidence_agreement: int
    tool_compatibility: int
    extraction_confidence: float
    sort_key: tuple[int | float | str, ...]

    def to_mapping(self) -> dict[str, Any]:
        return {
            "experience_id": self.experience_id,
            "original_rank": self.original_rank,
            "observed_contradictions": list(self.observed_contradictions),
            "active_contradictions": list(self.active_contradictions),
            "eligible": self.eligible,
            "precondition_status": self.precondition_status.value,
            "evidence_support": self.evidence_support.value,
            "repair_target_agreement": self.repair_target_agreement,
            "trigger_evidence_agreement": self.trigger_evidence_agreement,
            "tool_compatibility": self.tool_compatibility,
            "extraction_confidence": self.extraction_confidence,
            "sort_key": list(self.sort_key),
        }


@dataclass(frozen=True)
class PaperSelectionDecision:
    variant: SelectorVariant
    action: SelectionAction
    rank1_experience_id: str
    selected_experience_id: str
    selected_original_rank: int
    selection_changed: bool
    abstained: bool
    reason_codes: tuple[str, ...]
    minimum_extraction_confidence: float
    candidate_evaluations: tuple[PaperCandidateEvaluation, ...]
    method_version: str = "proper_paper_2026_v0_1_frozen"

    def __post_init__(self) -> None:
        if not self.reason_codes:
            raise ValueError("paper selection decision requires a reason code")
        expected_changed = self.selected_experience_id != self.rank1_experience_id
        if self.selection_changed != expected_changed:
            raise ValueError("selection_changed is inconsistent with selected identity")
        if self.action == SelectionAction.SELECT and not self.selection_changed:
            raise ValueError("select action must change Rank-1")
        if self.action != SelectionAction.SELECT and self.selection_changed:
            raise ValueError("only select action may change Rank-1")
        if self.abstained != (self.action == SelectionAction.ABSTAIN):
            raise ValueError("abstained flag is inconsistent with action")
        by_id = {value.experience_id: value for value in self.candidate_evaluations}
        if len(by_id) != len(self.candidate_evaluations):
            raise ValueError("candidate evaluations must have unique identities")
        if self.rank1_experience_id not in by_id:
            raise ValueError("Rank-1 identity is absent from candidate evaluations")
        if by_id[self.rank1_experience_id].original_rank != 1:
            raise ValueError("rank1_experience_id must identify original Rank-1")
        if self.selected_experience_id not in by_id:
            raise ValueError("selected identity is absent from candidate evaluations")
        if by_id[self.selected_experience_id].original_rank != self.selected_original_rank:
            raise ValueError("selected_original_rank is inconsistent with selected identity")

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "method_version": self.method_version,
            "variant": self.variant.value,
            "action": self.action.value,
            "rank1_experience_id": self.rank1_experience_id,
            "selected_experience_id": self.selected_experience_id,
            "selected_original_rank": self.selected_original_rank,
            "selection_changed": self.selection_changed,
            "abstained": self.abstained,
            "reason_codes": list(self.reason_codes),
            "minimum_extraction_confidence": self.minimum_extraction_confidence,
            "candidate_evaluations": [
                value.to_mapping() for value in self.candidate_evaluations
            ],
        }
