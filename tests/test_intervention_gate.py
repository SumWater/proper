from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from failure_memory.intervention_gate import (  # noqa: E402
    applicability_intervention_label,
    extract_gate_features,
    ordered_top10,
)


class InterventionGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        manifest = json.loads(
            (ROOT / "outputs" / "candidate_selection" / "selection_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        cls.record = manifest["records"][0]

    def test_original_rank_order_is_complete(self) -> None:
        values = ordered_top10(self.record)
        self.assertEqual(
            [item["candidate"]["original_rank"] for item in values],
            list(range(1, 11)),
        )

    def test_evaluator_label_mutation_cannot_change_features(self) -> None:
        changed = copy.deepcopy(self.record)
        for item in changed["proper_top10"]:
            item["evaluator_only_environment_applicable"] = not bool(
                item["evaluator_only_environment_applicable"]
            )
        self.assertEqual(
            extract_gate_features(self.record), extract_gate_features(changed)
        )

    def test_features_exclude_ids_scores_and_raw_values(self) -> None:
        features = extract_gate_features(self.record)
        serialized = json.dumps(features, ensure_ascii=False, sort_keys=True)
        self.assertNotIn(str(self.record["instance_id"]), serialized)
        self.assertNotIn("experience::", serialized)
        self.assertNotIn("tfidf", serialized.lower())
        self.assertNotIn("environment_applicability", serialized)

    def test_label_is_separate_from_feature_extraction(self) -> None:
        value = applicability_intervention_label(self.record)
        self.assertIsInstance(value, bool)

    def test_feature_extraction_is_deterministic(self) -> None:
        self.assertEqual(
            extract_gate_features(self.record), extract_gate_features(self.record)
        )


if __name__ == "__main__":
    unittest.main()
