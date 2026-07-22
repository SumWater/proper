from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from candidate_audit import (  # noqa: E402
    audit,
    load_development_config,
    observable_candidate_policy,
    stable_split_key,
)


class ProperV1AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = audit()
        cls.config = load_development_config()

    def test_split_key_is_deterministic_and_seeded(self) -> None:
        value = "instance"
        self.assertEqual(stable_split_key("a", value), stable_split_key("a", value))
        self.assertNotEqual(stable_split_key("a", value), stable_split_key("b", value))

    def test_candidate_policy_is_derived_from_natural_text(self) -> None:
        self.assertEqual(
            observable_candidate_policy("I retried the original tool call once."),
            "retry_original_call_once",
        )
        self.assertEqual(
            observable_candidate_policy("I corrected the missing arguments."),
            "repair_missing_arguments",
        )
        self.assertEqual(
            observable_candidate_policy("I stopped without another tool call."),
            "stop_and_report",
        )

    def test_audit_has_332_targets_and_fixed_top10(self) -> None:
        records = self.report["records"]
        self.assertEqual(len(records), 332)
        self.assertEqual(len({item["instance_id"] for item in records}), 332)
        self.assertTrue(
            all(len(item["retrieval"]["candidates_top10"]) == 10 for item in records)
        )

    def test_validation_case_outcomes_are_not_exposed(self) -> None:
        self.assertTrue(
            self.report["audit_boundary"]["validation_case_level_outcomes_sealed"]
        )
        self.assertFalse(self.report["audit_boundary"]["new_model_output_generated"])
        for record in self.report["records"]:
            self.assertNotIn("conditions", record)
            self.assertNotIn("recovery_validity_outcome", str(record))

    def test_fixed_split_counts_and_no_overlap(self) -> None:
        records = self.report["records"]
        design = {
            item["instance_id"]
            for item in records
            if item["development_partition"] == "conflict_rule_design"
        }
        validation = {
            item["instance_id"]
            for item in records
            if item["development_partition"] == "conflict_sealed_validation"
        }
        self.assertEqual(len(design), self.config["development_split"]["rule_design_count"])
        self.assertEqual(
            len(validation), self.config["development_split"]["sealed_validation_count"]
        )
        self.assertFalse(design & validation)

    def test_formal_prompts_reconstruct_without_memory_rewrite(self) -> None:
        bank = self.report["memory_bank_audit"]
        self.assertEqual(bank["fixed_memory_bank_count"], 100)
        self.assertEqual(
            bank["matched_applicable_prompt_reconstructed_without_rewrite_count"], 104
        )


if __name__ == "__main__":
    unittest.main()
