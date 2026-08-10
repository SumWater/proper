"""Deterministic paired-binary statistics for the paper analysis plan."""

from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class PairedBinarySummary:
    pair_count: int
    baseline_successes: int
    treatment_successes: int
    positive_discordant: int
    negative_discordant: int
    paired_risk_difference: float
    exact_two_sided_mcnemar_p: float

    def to_mapping(self) -> dict[str, int | float]:
        return {
            "pair_count": self.pair_count,
            "baseline_successes": self.baseline_successes,
            "treatment_successes": self.treatment_successes,
            "positive_discordant": self.positive_discordant,
            "negative_discordant": self.negative_discordant,
            "paired_risk_difference": self.paired_risk_difference,
            "exact_two_sided_mcnemar_p": self.exact_two_sided_mcnemar_p,
        }


def _binary(value: bool | int, field: str) -> int:
    if value not in (False, True, 0, 1):
        raise ValueError(f"{field} values must be binary")
    return int(value)


def exact_two_sided_mcnemar(positive: int, negative: int) -> float:
    if positive < 0 or negative < 0:
        raise ValueError("discordant counts must be non-negative")
    discordant = positive + negative
    if discordant == 0:
        return 1.0
    lower = min(positive, negative)
    probability = sum(math.comb(discordant, value) for value in range(lower + 1))
    probability /= 2**discordant
    return min(1.0, 2.0 * probability)


def paired_binary_summary(
    baseline: Sequence[bool | int], treatment: Sequence[bool | int]
) -> PairedBinarySummary:
    if not baseline or len(baseline) != len(treatment):
        raise ValueError("paired binary inputs must be non-empty and equal length")
    pairs = [
        (_binary(left, "baseline"), _binary(right, "treatment"))
        for left, right in zip(baseline, treatment, strict=True)
    ]
    positive = sum(left == 0 and right == 1 for left, right in pairs)
    negative = sum(left == 1 and right == 0 for left, right in pairs)
    baseline_successes = sum(left for left, _ in pairs)
    treatment_successes = sum(right for _, right in pairs)
    return PairedBinarySummary(
        pair_count=len(pairs),
        baseline_successes=baseline_successes,
        treatment_successes=treatment_successes,
        positive_discordant=positive,
        negative_discordant=negative,
        paired_risk_difference=(treatment_successes - baseline_successes) / len(pairs),
        exact_two_sided_mcnemar_p=exact_two_sided_mcnemar(positive, negative),
    )


def derived_seed(base_seed: int, analysis_id: str) -> int:
    if not analysis_id:
        raise ValueError("analysis_id cannot be empty")
    payload = f"{base_seed}:{analysis_id}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _linear_percentile(sorted_values: Sequence[float], probability: float) -> float:
    if not sorted_values or not 0.0 <= probability <= 1.0:
        raise ValueError("invalid percentile input")
    position = probability * (len(sorted_values) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(sorted_values[lower])
    weight = position - lower
    return float(sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight)


def paired_bootstrap_risk_difference_ci(
    baseline: Sequence[bool | int],
    treatment: Sequence[bool | int],
    *,
    replicates: int,
    confidence_level: float,
    seed: int,
) -> tuple[float, float]:
    if not baseline or len(baseline) != len(treatment):
        raise ValueError("paired bootstrap inputs must be non-empty and equal length")
    if replicates < 1000:
        raise ValueError("paired bootstrap requires at least 1000 replicates")
    if not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence_level must be in (0, 1)")
    differences = [
        _binary(right, "treatment") - _binary(left, "baseline")
        for left, right in zip(baseline, treatment, strict=True)
    ]
    generator = random.Random(seed)
    size = len(differences)
    estimates = []
    for _ in range(replicates):
        estimates.append(
            sum(differences[generator.randrange(size)] for _ in range(size)) / size
        )
    estimates.sort()
    alpha = 1.0 - confidence_level
    return (
        _linear_percentile(estimates, alpha / 2.0),
        _linear_percentile(estimates, 1.0 - alpha / 2.0),
    )


def holm_adjust(p_values: Mapping[str, float]) -> dict[str, float]:
    if not p_values:
        raise ValueError("Holm adjustment requires at least one p-value")
    for label, value in p_values.items():
        if not label or not 0.0 <= value <= 1.0:
            raise ValueError("Holm labels must be non-empty and p-values in [0, 1]")
    ordered = sorted(p_values.items(), key=lambda item: (item[1], item[0]))
    count = len(ordered)
    previous = 0.0
    adjusted: dict[str, float] = {}
    for index, (label, value) in enumerate(ordered):
        current = min(1.0, (count - index) * value)
        current = max(previous, current)
        adjusted[label] = current
        previous = current
    return {label: adjusted[label] for label in sorted(adjusted)}
