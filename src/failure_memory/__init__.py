"""Core types for the failure-memory compatibility pilot."""

from .contracts import (
    Budget,
    EvaluationResult,
    FailureClass,
    RecoveryContract,
    RecoveryPolicy,
    RecoveryTrace,
)
from .retrieval import Experience, FailureQuery, SourceBlindTfidfRetriever
from .utilization import AgentDecision, DecisionKind, RunOutcome

__all__ = [
    "Budget",
    "EvaluationResult",
    "FailureClass",
    "RecoveryContract",
    "RecoveryPolicy",
    "RecoveryTrace",
    "Experience",
    "FailureQuery",
    "SourceBlindTfidfRetriever",
    "AgentDecision",
    "DecisionKind",
    "RunOutcome",
]
