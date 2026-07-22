"""Dependency-light inference for the frozen applicability intervention gate."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping


def vectorized_feature_values(features: Mapping[str, Any]) -> dict[str, float]:
    """Reproduce DictVectorizer naming for the frozen scalar feature dictionary."""

    values: dict[str, float] = {}
    for key, value in features.items():
        if isinstance(value, str):
            values[f"{key}={value}"] = 1.0
        elif isinstance(value, bool):
            values[key] = float(value)
        elif isinstance(value, (int, float)):
            values[key] = float(value)
        else:
            raise TypeError(f"unsupported frozen-gate feature type for {key}: {type(value)}")
    return values


def sigmoid(logit: float) -> float:
    if logit >= 0:
        inverse = math.exp(-logit)
        return 1.0 / (1.0 + inverse)
    exponential = math.exp(logit)
    return exponential / (1.0 + exponential)


@dataclass(frozen=True)
class FrozenGateDecision:
    probability: float
    threshold: float
    intervene: bool


def score_frozen_gate(
    features: Mapping[str, Any], model_payload: Mapping[str, Any]
) -> FrozenGateDecision:
    coefficients = {
        str(item["feature"]): float(item["coefficient"])
        for item in model_payload["nonzero_coefficients"]
    }
    vectorized = vectorized_feature_values(features)
    logit = float(model_payload["intercept"])
    logit += sum(
        coefficients.get(feature_name, 0.0) * value
        for feature_name, value in vectorized.items()
    )
    probability = sigmoid(logit)
    threshold = float(model_payload["decision_probability_at_least"])
    return FrozenGateDecision(
        probability=probability,
        threshold=threshold,
        intervene=probability >= threshold,
    )
