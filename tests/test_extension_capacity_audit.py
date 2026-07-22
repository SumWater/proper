from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from extension_capacity_audit import (  # noqa: E402
    alias_summary,
    best_replacement,
    run_audit,
    structural_signature,
)


class ExtensionCapacityAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = run_audit()

    def test_frozen_population_is_partitioned_without_model_outputs(self) -> None:
        payload = self.payload
        self.assertEqual(payload["population"]["target_count"], 332)
        self.assertFalse(payload["boundary"]["model_loaded"])
        self.assertFalse(payload["boundary"]["model_outputs_read"])
        self.assertFalse(payload["boundary"]["gpu_run_authorized"])
        self.assertEqual(
            sum(item["target_count"] for item in payload["families"].values()), 332
        )

    def test_native_family_counts_are_stable(self) -> None:
        families = self.payload["families"]
        self.assertEqual(families["schema_drift"]["target_count"], 94)
        self.assertEqual(families["timeout"]["target_count"], 92)
        self.assertEqual(families["authorization"]["target_count"], 54)
        self.assertEqual(families["argument_omission_reference"]["target_count"], 92)

    def test_top10_never_has_less_capacity_than_top5(self) -> None:
        for family in self.payload["families"].values():
            top5 = family["candidate_depths"]["5"]
            top10 = family["candidate_depths"]["10"]
            self.assertGreaterEqual(
                top10["applicable_candidate_available_count"],
                top5["applicable_candidate_available_count"],
            )
            self.assertGreaterEqual(
                top10["rank1_inapplicable_with_replacement_count"],
                top5["rank1_inapplicable_with_replacement_count"],
            )

    def test_structural_signature_excludes_ids_and_evaluator_labels(self) -> None:
        record = {
            "instance_id": "secret::provenance",
            "target_features": {
                "state": "timeout",
                "error_code": "timeout",
                "tool_name": "read_file",
                "missing_fields": [],
                "public_schema_fields": ["path"],
                "public_required_fields": ["path"],
                "schema_signature": "schema",
                "failed_argument_paths": ["/path"],
                "repeated_same_call_count": 1,
            },
            "evaluator_only": {"baseline_environment_applicable": True},
        }
        signature = structural_signature(record)
        serialized = str(signature)
        self.assertNotIn("secret", serialized)
        self.assertNotIn("provenance", serialized)
        self.assertNotIn("applicable", serialized)

    def test_authorization_alias_blocks_direct_one_step_generalization(self) -> None:
        aliasing = self.payload["observable_aliasing"]
        self.assertEqual(
            aliasing["schema_drift_vs_argument_omission"]["shared_signature_group_count"],
            0,
        )
        self.assertTrue(
            aliasing["schema_drift_vs_argument_omission"][
                "current_structural_prefix_is_fully_identifying"
            ]
        )
        self.assertGreater(
            aliasing["authorization_transient_vs_persistent"][
                "shared_signature_group_count"
            ],
            0,
        )
        self.assertFalse(
            self.payload["planning_decision"]["direct_one_step_generalization_ready"]
        )


if __name__ == "__main__":
    unittest.main()
