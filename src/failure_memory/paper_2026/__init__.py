"""Paper-level PROPER selector with prespecified component ablations."""

from .boundary import assert_paper_observable_payload, candidate_from_mapping, state_from_mapping
from .contracts import (
    PaperCandidateEvaluation,
    PaperSelectionDecision,
    SelectionAction,
    SelectorVariant,
)
from .selector import select_from_mappings, select_memory
from .statistics import (
    PairedBinarySummary,
    derived_seed,
    exact_two_sided_mcnemar,
    holm_adjust,
    paired_binary_summary,
    paired_bootstrap_risk_difference_ci,
)

__all__ = [
    "PaperCandidateEvaluation",
    "PaperSelectionDecision",
    "PairedBinarySummary",
    "SelectionAction",
    "SelectorVariant",
    "assert_paper_observable_payload",
    "candidate_from_mapping",
    "derived_seed",
    "exact_two_sided_mcnemar",
    "holm_adjust",
    "paired_binary_summary",
    "paired_bootstrap_risk_difference_ci",
    "select_from_mappings",
    "select_memory",
    "state_from_mapping",
]
