from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from confirmatory_transient_authz_v1 import (  # noqa: E402
    aggregate_pairs,
    cpu_dry_run,
    load_capacity,
    load_config,
)
from failure_memory.confirmatory import PairIndicators  # noqa: E402


class ConfirmatoryTransientAuthzV1Tests(unittest.TestCase):
    def test_frozen_scope_and_conditions(self) -> None:
        config = load_config()
        self.assertTrue(config["cohort"]["persistent_authorization_excluded"])
        self.assertEqual(
            config["conditions"]["fixed_order"],
            ["tfidf_rank1_memory", "proper_transient_authz_memory"],
        )
        self.assertEqual(config["frozen_capacity"]["expected_all_target_count"], 175)
        self.assertEqual(config["frozen_capacity"]["expected_primary_pair_count"], 53)
        self.assertEqual(
            config["frozen_capacity"]["expected_unique_generation_count"], 228
        )

    def test_capacity_result_is_hash_locked(self) -> None:
        config = load_config()
        payload = load_capacity(config)
        self.assertEqual(len(payload["records"]), 175)
        self.assertEqual(sum(item["selection_changed"] for item in payload["records"]), 53)
        lock = json.loads(
            (ROOT / "configs" / "transient_authz_capacity_v1.result.lock.json").read_text(
                encoding="utf-8"
            )
        )
        for key in ("screening", "linux_log"):
            item = lock[key]
            actual = hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest()
            self.assertEqual(actual, item["sha256"], key)
        self.assertFalse(lock["model_outputs_generated"])

    def test_cpu_dry_run_reads_neither_test_nor_model(self) -> None:
        result = cpu_dry_run(load_config())
        self.assertFalse(result["model_loaded"])
        self.assertFalse(result["public_test_read"])
        self.assertTrue(result["synthetic_non_model_output"])
        self.assertEqual(result["capacity_target_count"], 175)
        self.assertEqual(result["primary_pair_count"], 53)
        self.assertEqual(result["condition_count"], 2)
        self.assertEqual(result["distinct_prompt_count"], 2)

    def test_primary_direction_is_proper_greater_than_rank1(self) -> None:
        indicators = [
            PairIndicators(False, True, True, False, True, False),
            PairIndicators(False, False, False, False, True, False),
        ]
        result = aggregate_pairs(indicators, [False, True], [True, True], 0.05)
        self.assertEqual(result["paired_positive_transfer_count"], 1)
        self.assertEqual(result["paired_negative_transfer_count"], 0)
        self.assertEqual(result["hypothesis_direction"], "ppt_greater_than_pnt")

    def test_formal_sources_match_lock(self) -> None:
        lock_path = ROOT / "configs" / "confirmatory_transient_authz_v1.lock.json"
        if not lock_path.exists():
            self.skipTest("formal source lock is created after source files are finalized")
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        for key in (
            "config",
            "runner",
            "selector",
            "result_schema",
            "preregistration",
            "capacity_result_lock",
        ):
            item = lock[key]
            actual = hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest()
            self.assertEqual(actual, item["sha256"], key)
        self.assertFalse(lock["model_outputs_generated"])
        self.assertFalse(lock["gpu_run_authorized"])


if __name__ == "__main__":
    unittest.main()
