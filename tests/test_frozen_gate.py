from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import numpy as np
import yaml
from sklearn.feature_extraction import DictVectorizer


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments" / "proper_v1"))

from applicability_intervention_gate import make_model  # noqa: E402
from failure_memory.frozen_gate import score_frozen_gate  # noqa: E402
from failure_memory.intervention_gate import (  # noqa: E402
    applicability_intervention_label,
    extract_gate_features,
)


class FrozenGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = yaml.safe_load(
            (ROOT / "configs" / "proper_v1" / "applicability_intervention_gate.yaml").read_text(
                encoding="utf-8"
            )
        )
        cls.manifest = json.loads(
            (ROOT / "outputs" / "proper_v1" / "candidate_selection" / "selection_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        cls.artifact = json.loads(
            (ROOT / "outputs" / "proper_v1" / "proper_gate" / "cross_validation.json").read_text(
                encoding="utf-8"
            )
        )

    def test_dependency_light_score_matches_fitted_sklearn_model(self) -> None:
        records = self.manifest["records"]
        features = [extract_gate_features(record) for record in records]
        labels = np.asarray(
            [int(applicability_intervention_label(record)) for record in records]
        )
        vectorizer = DictVectorizer(sparse=True, sort=True)
        matrix = vectorizer.fit_transform(features)
        model = make_model(self.config)
        model.fit(matrix, labels)
        sklearn_probabilities = model.predict_proba(matrix)[:, 1]
        frozen_probabilities = np.asarray(
            [
                score_frozen_gate(feature, self.artifact["final_model"]).probability
                for feature in features
            ]
        )
        np.testing.assert_allclose(
            frozen_probabilities, sklearn_probabilities, rtol=0.0, atol=1e-12
        )

    def test_threshold_is_frozen_at_point_seven_five(self) -> None:
        features = extract_gate_features(self.manifest["records"][0])
        decision = score_frozen_gate(features, self.artifact["final_model"])
        self.assertEqual(decision.threshold, 0.75)
        self.assertEqual(decision.intervene, decision.probability >= 0.75)


if __name__ == "__main__":
    unittest.main()
