from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from observable_identifiability_audit import (  # noqa: E402
    intervention_label,
    observable_signature,
    summarize_level,
)


def candidate(rank: int, policy: str, applicable: bool) -> dict:
    return {
        "candidate": {
            "original_rank": rank,
            "policy_from_text": policy,
            "repair_targets": ["path"] if policy == "repair" else [],
            "source_failure": {
                "state": "argument_omission",
                "tool_name": "read_file",
            },
        },
        "evaluator_only_environment_applicable": applicable,
    }


def record(instance_id: str, baseline_applicable: bool, replacement: bool) -> dict:
    return {
        "instance_id": instance_id,
        "target_features": {
            "state": "argument_omission",
            "error_code": "missing_required_arg",
            "tool_name": "read_file",
            "missing_fields": ["path"],
            "public_schema_fields": ["path"],
            "public_required_fields": ["path"],
            "schema_signature": "schema",
            "failed_argument_paths": [],
            "repeated_same_call_count": 1,
        },
        "proper_top10": [
            candidate(1, "retry", baseline_applicable),
            candidate(2, "repair", replacement),
        ],
    }


class ObservableIdentifiabilityAuditTests(unittest.TestCase):
    def test_intervention_requires_bad_rank1_and_available_replacement(self) -> None:
        self.assertTrue(intervention_label(record("a::one", False, True)))
        self.assertFalse(intervention_label(record("a::two", True, True)))
        self.assertFalse(intervention_label(record("a::three", False, False)))

    def test_signature_excludes_instance_and_evaluator_labels(self) -> None:
        first = record("a::one", False, True)
        second = record("b::two", True, False)
        self.assertEqual(
            observable_signature(first, "normalized_structural_and_baseline_policy"),
            observable_signature(second, "normalized_structural_and_baseline_policy"),
        )

    def test_mixed_group_is_reported_as_ambiguous(self) -> None:
        rows = [record("a::one", False, True), record("b::two", True, True)]
        result = summarize_level(rows, "normalized_structural_and_baseline_policy")
        self.assertEqual(result["ambiguous_group_count"], 1)
        self.assertEqual(result["ambiguous_target_count"], 2)
        self.assertEqual(result["deterministic_majority_accuracy"], 0.5)

    def test_candidate_profile_signature_uses_only_public_candidate_features(self) -> None:
        value = observable_signature(
            record("a::one", False, True),
            "normalized_structural_with_candidate_profiles",
        )
        self.assertEqual(len(value["candidate_profiles"]), 2)
        self.assertNotIn("evaluator_only_environment_applicable", str(value))


if __name__ == "__main__":
    unittest.main()
