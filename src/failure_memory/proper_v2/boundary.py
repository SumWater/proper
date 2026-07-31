"""Strict observable-input boundary for unified PROPER v2."""

from __future__ import annotations

from typing import Any, Mapping

from .contracts import (
    MemoryPolicyCard,
    ObservableFailure,
    ObservableRecoveryState,
)


FORBIDDEN_INPUT_KEYS = frozenset(
    {
        "fault_plan",
        "fault_type",
        "recoverability",
        "gold_summary",
        "gold_trajectory",
        "success_criteria",
        "provenance",
        "recommended_policy",
        "environment_applicability",
        "evaluator_only_environment_applicable",
        "recovery_validity",
        "recovery_validity_outcome",
        "task_completion_outcome",
        "safety_violation_outcome",
        "matched_applicable_experience_id",
        "difficulty",
        "solution",
        "faults",
        "original_error_code",
    }
)


def assert_observable_payload(value: Any, path: str = "$") -> None:
    """Reject evaluator, oracle, and injection-only fields recursively."""

    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).lower()
            if normalized in FORBIDDEN_INPUT_KEYS:
                raise ValueError(f"forbidden PROPER v2 input at {path}.{key}")
            assert_observable_payload(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            assert_observable_payload(child, f"{path}[{index}]")


def observable_failure_from_mapping(payload: Mapping[str, Any]) -> ObservableFailure:
    assert_observable_payload(payload)
    return ObservableFailure.from_mapping(payload)


def observable_recovery_state_from_mapping(
    payload: Mapping[str, Any],
) -> ObservableRecoveryState:
    assert_observable_payload(payload)
    return ObservableRecoveryState.from_mapping(payload)


def memory_policy_card_from_mapping(payload: Mapping[str, Any]) -> MemoryPolicyCard:
    assert_observable_payload(payload)
    return MemoryPolicyCard.from_mapping(payload)
