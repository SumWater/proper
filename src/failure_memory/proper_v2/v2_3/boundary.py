"""Strict observable-input boundary for PROPER v2.3 execution contracts."""

from __future__ import annotations

from typing import Any, Mapping

from ..boundary import assert_observable_payload
from .contracts import ActionEffectContract, ActionSpec


V2_3_FORBIDDEN_INPUT_KEYS = frozenset(
    {
        "scenario_name",
        "semantic_family",
        "gold_action",
        "gold_label",
        "evaluator_outcome",
        "prior_model_result",
        "model_outcome",
    }
)


def _assert_v2_3_specific_keys(value: Any, path: str) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).lower()
            if normalized in V2_3_FORBIDDEN_INPUT_KEYS:
                raise ValueError(f"forbidden PROPER v2.3 input at {path}.{key}")
            _assert_v2_3_specific_keys(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _assert_v2_3_specific_keys(child, f"{path}[{index}]")


def assert_v2_3_observable_payload(value: Any, path: str = "$") -> None:
    assert_observable_payload(value, path)
    _assert_v2_3_specific_keys(value, path)


def observable_action_from_mapping(payload: Mapping[str, Any]) -> ActionSpec:
    assert_v2_3_observable_payload(payload)
    return ActionSpec.from_mapping(payload)


def action_effect_contract_from_mapping(
    payload: Mapping[str, Any],
) -> ActionEffectContract:
    assert_v2_3_observable_payload(payload)
    return ActionEffectContract.from_mapping(payload)
