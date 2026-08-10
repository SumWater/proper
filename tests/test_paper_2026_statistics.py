from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from failure_memory.paper_2026.statistics import (  # noqa: E402
    derived_seed,
    exact_two_sided_mcnemar,
    holm_adjust,
    paired_binary_summary,
    paired_bootstrap_risk_difference_ci,
)


def pairs(
    *, total: int, baseline_successes: int, positive: int, negative: int
) -> tuple[list[int], list[int]]:
    both_success = baseline_successes - negative
    both_failure = total - both_success - positive - negative
    if min(both_success, both_failure, positive, negative) < 0:
        raise ValueError("invalid synthetic paired table")
    baseline = [1] * both_success + [0] * positive + [1] * negative + [0] * both_failure
    treatment = [1] * both_success + [1] * positive + [0] * negative + [0] * both_failure
    return baseline, treatment


class PaperStatisticsTests(unittest.TestCase):
    def test_argument_omission_historical_table(self) -> None:
        baseline, treatment = pairs(
            total=115, baseline_successes=99, positive=10, negative=0
        )
        summary = paired_binary_summary(baseline, treatment)
        self.assertEqual(summary.treatment_successes, 109)
        self.assertEqual(summary.positive_discordant, 10)
        self.assertEqual(summary.negative_discordant, 0)
        self.assertAlmostEqual(summary.paired_risk_difference, 10 / 115)
        self.assertAlmostEqual(summary.exact_two_sided_mcnemar_p, 2 / 1024)

    def test_transient_authorization_historical_table(self) -> None:
        baseline, treatment = pairs(
            total=53, baseline_successes=34, positive=15, negative=0
        )
        summary = paired_binary_summary(baseline, treatment)
        self.assertEqual(summary.treatment_successes, 49)
        self.assertAlmostEqual(summary.paired_risk_difference, 15 / 53)
        self.assertAlmostEqual(summary.exact_two_sided_mcnemar_p, 2 / 32768)

    def test_zero_discordance_has_unit_p_value(self) -> None:
        self.assertEqual(exact_two_sided_mcnemar(0, 0), 1.0)

    def test_paired_bootstrap_is_deterministic_and_contains_effect(self) -> None:
        baseline, treatment = pairs(
            total=115, baseline_successes=99, positive=10, negative=0
        )
        seed = derived_seed(20260809, "qwen:argument_omission:proper_vs_tfidf")
        first = paired_bootstrap_risk_difference_ci(
            baseline,
            treatment,
            replicates=2000,
            confidence_level=0.95,
            seed=seed,
        )
        second = paired_bootstrap_risk_difference_ci(
            baseline,
            treatment,
            replicates=2000,
            confidence_level=0.95,
            seed=seed,
        )
        self.assertEqual(first, second)
        self.assertLessEqual(first[0], 10 / 115)
        self.assertGreaterEqual(first[1], 10 / 115)

    def test_holm_adjustment_is_monotone_and_label_order_independent(self) -> None:
        values = {"b": 0.04, "a": 0.01, "c": 0.03}
        adjusted = holm_adjust(values)
        self.assertEqual(adjusted, {"a": 0.03, "b": 0.06, "c": 0.06})
        self.assertEqual(adjusted, holm_adjust(dict(reversed(list(values.items())))))

    def test_nonbinary_values_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "binary"):
            paired_binary_summary([0, 2], [1, 1])


if __name__ == "__main__":
    unittest.main()
