from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "proper_v2"))

from timeout_pair_preparation_v2 import (  # noqa: E402
    cpu_dry_run,
    load_capacity,
    load_config,
)


class TimeoutPairPreparationV2Tests(unittest.TestCase):
    def test_frozen_capacity_identity_and_counts(self) -> None:
        config = load_config()
        capacity = load_capacity(config)
        self.assertEqual(len(capacity["records"]), 177)
        self.assertEqual(
            sum(item["selection_changed"] for item in capacity["records"]), 32
        )
        self.assertTrue(
            capacity["screening"]["future_protocol_preparation_authorized"]
        )

    def test_preparation_stage_cannot_authorize_gpu(self) -> None:
        config = load_config()
        self.assertFalse(
            config["boundary"]["gpu_run_authorized_at_preparation_stage"]
        )

    def test_planned_calls_equal_all_targets_plus_changed_pairs(self) -> None:
        config = load_config()
        frozen = config["frozen_capacity"]
        expected = int(frozen["expected_all_target_count"]) + int(
            frozen["expected_primary_pair_count"]
        )
        self.assertEqual(
            int(frozen["expected_planned_model_call_count"]), expected
        )

    def test_cpu_dry_run_reads_no_public_test_or_model_output(self) -> None:
        result = cpu_dry_run(load_config())
        self.assertFalse(result["model_loaded"])
        self.assertFalse(result["public_test_read"])
        self.assertTrue(result["synthetic_non_model_output"])
        self.assertEqual(result["capacity_target_count"], 177)
        self.assertEqual(result["primary_pair_count"], 32)


if __name__ == "__main__":
    unittest.main()
