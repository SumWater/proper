"""Fail-closed observable-input boundary for the paper selector."""

from __future__ import annotations

from typing import Any, Mapping

from failure_memory.proper_v2.boundary import (
    memory_policy_card_from_mapping,
    observable_failure_from_mapping,
    observable_recovery_state_from_mapping,
)
from failure_memory.proper_v2.contracts import (
    MemoryPolicyCard,
    ObservableFailure,
    ObservableRecoveryState,
)


PAPER_FORBIDDEN_INPUT_KEYS = frozenset(
    {
        "applicability",
        "applicable",
        "benchmark",
        "benchmark_name",
        "benchmark_scenario",
        "condition",
        "condition_name",
        "dataset",
        "dataset_name",
        "fault_label",
        "gold_action",
        "hidden_label",
        "method",
        "method_name",
        "model_outcome",
        "oracle",
        "prior_model_outcome",
        "scenario",
        "scenario_name",
        "selector_name",
        "split",
        "target_label",
    }
)


def assert_paper_observable_payload(value: Any, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            if normalized in PAPER_FORBIDDEN_INPUT_KEYS:
                raise ValueError(f"forbidden paper selector input at {path}.{key}")
            assert_paper_observable_payload(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            assert_paper_observable_payload(child, f"{path}[{index}]")


def state_from_mapping(
    payload: Mapping[str, Any],
) -> ObservableFailure | ObservableRecoveryState:
    assert_paper_observable_payload(payload)
    version = int(payload.get("schema_version", 0))
    if version == 1:
        return observable_failure_from_mapping(payload)
    if version == 2:
        return observable_recovery_state_from_mapping(payload)
    raise ValueError("unsupported paper observable-state schema_version")


def candidate_from_mapping(payload: Mapping[str, Any]) -> MemoryPolicyCard:
    assert_paper_observable_payload(payload)
    return memory_policy_card_from_mapping(payload)
