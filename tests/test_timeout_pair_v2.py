from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments" / "proper_v2"))

from failure_memory.confirmatory import PairIndicators
from timeout_pair_v2 import (
    aggregate_pairs,
    cpu_dry_run,
    load_config,
    verify_formal_lock,
)


def indicator(*, positive: bool = False, negative: bool = False) -> PairIndicators:
    return PairIndicators(
        paired_negative_transfer=negative,
        paired_positive_transfer=positive,
        memory_induced_action_change=positive or negative,
        inapplicable_memory_harm=negative,
        strict_policy_adoption=positive,
        policy_followed_harm=False,
    )


class TimeoutPairV2Tests(unittest.TestCase):
    def test_formal_config_fixes_primary_population(self) -> None:
        config = load_config()
        self.assertEqual(config["primary_endpoint"]["pair_count"], 32)
        self.assertEqual(config["preparation"]["expected_model_call_count"], 209)
        self.assertEqual(
            config["preparation"]["expected_global_distinct_prompt_count"], 198
        )

    def test_cpu_dry_run_reads_no_model_or_public_test(self) -> None:
        result = cpu_dry_run(load_config())
        self.assertFalse(result["model_loaded"])
        self.assertFalse(result["model_outputs_read"])
        self.assertFalse(result["public_test_read"])
        self.assertTrue(result["prepared_manifest_sha256_matches"])
        self.assertEqual(result["primary_pair_count"], 32)

    def test_formal_lock_verifies_all_frozen_sources(self) -> None:
        lock = verify_formal_lock()
        self.assertTrue(lock["gpu_run_authorized"])
        self.assertFalse(lock["model_outputs_generated"])
        self.assertEqual(lock["counts"]["primary_pair_count"], 32)

    def test_primary_direction_and_condition_counts_are_explicit(self) -> None:
        indicators = [indicator(positive=True) for _ in range(10)] + [
            indicator(negative=True)
        ]
        baseline = [False] * 10 + [True]
        proper = [True] * 10 + [False]
        result = aggregate_pairs(indicators, baseline, proper, alpha=0.05)
        self.assertEqual(result["baseline_recovery_validity_count"], 1)
        self.assertEqual(result["proper_recovery_validity_count"], 10)
        self.assertEqual(result["paired_positive_transfer_count"], 10)
        self.assertEqual(result["paired_negative_transfer_count"], 1)
        self.assertTrue(result["directional_hypothesis_supported"])


if __name__ == "__main__":
    unittest.main()
