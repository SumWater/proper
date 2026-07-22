from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from candidate_manifest import verify_rule_lock  # noqa: E402


class ProperV1DevelopmentResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.output = json.loads(
            (ROOT / "outputs" / "candidate_selection" / "selection_manifest.json").read_text(
                encoding="utf-8"
            )
        )

    def test_locked_rule_hashes_still_match(self) -> None:
        lock = verify_rule_lock()
        self.assertFalse(lock["validation_outcomes_unsealed"])

    def test_manifest_has_332_unique_complete_selections(self) -> None:
        records = self.output["records"]
        self.assertEqual(len(records), 332)
        self.assertEqual(len({item["instance_id"] for item in records}), 332)
        self.assertTrue(all(len(item["proper_top10"]) == 10 for item in records))
        self.assertTrue(all(item["prompt"] for item in records))

    def test_validation_outcomes_remain_unused_and_unexposed(self) -> None:
        self.assertFalse(self.output["boundary"]["sealed_validation_outcomes_used"])
        for record in self.output["records"]:
            self.assertNotIn("conditions", record)
            self.assertNotIn("recovery_validity", record)

    def test_offline_counts_recompute_from_records(self) -> None:
        records = self.output["records"]
        rank1_applicable = [
            item
            for item in records
            if item["evaluator_only"]["baseline_environment_applicable"]
        ]
        conflicts = [
            item
            for item in records
            if not item["evaluator_only"]["baseline_environment_applicable"]
        ]
        exact_preserved = sum(not item["selection_changed"] for item in rank1_applicable)
        selected_conflict_applicable = sum(
            item["evaluator_only"]["selected_environment_applicable"]
            for item in conflicts
        )
        summary = self.output["offline_selection"]
        self.assertEqual(len(rank1_applicable), summary["rank1_applicable_count"])
        self.assertEqual(len(conflicts), summary["conflict_count"])
        self.assertEqual(
            exact_preserved,
            summary["rank1_applicable_exact_selection_preserved_count"],
        )
        self.assertEqual(
            selected_conflict_applicable,
            summary["conflict_selected_applicable_count"],
        )

    def test_frozen_offline_preservation_gate_stops_v1(self) -> None:
        summary = self.output["offline_selection"]
        self.assertEqual(summary["offline_preservation_gate_threshold"], 0.95)
        self.assertFalse(summary["offline_preservation_gate_pass"])


if __name__ == "__main__":
    unittest.main()
