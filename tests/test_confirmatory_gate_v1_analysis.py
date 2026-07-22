from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from analyze_confirmatory_gate_v1 import run_analysis  # noqa: E402


class ConfirmatoryGateV1AnalysisTests(unittest.TestCase):
    def test_independent_analysis_recomputes_frozen_primary_result(self) -> None:
        value = run_analysis()
        primary = value["primary_recomputed"]
        self.assertEqual(primary["pair_count"], 115)
        self.assertEqual(primary["paired_positive_transfer_count"], 10)
        self.assertEqual(primary["paired_negative_transfer_count"], 0)
        self.assertTrue(primary["directional_hypothesis_supported"])

    def test_effect_concentration_is_explicit(self) -> None:
        value = run_analysis()["effect_concentration"]
        self.assertTrue(value["all_improvements_single_tool"])
        self.assertTrue(value["all_improvements_single_selected_memory"])
        self.assertEqual(value["improvement_tool_counts"], {"get_doc": 10})

    def test_saved_analysis_matches_fixed_schema(self) -> None:
        analysis = json.loads(
            (ROOT / "outputs" / "confirmatory_gate_v1" / "analysis.json").read_text(
                encoding="utf-8"
            )
        )
        schema = json.loads(
            (
                ROOT
                / "schemas"
                / "confirmatory_gate_v1_analysis.schema.json"
            ).read_text(encoding="utf-8")
        )
        jsonschema.validate(analysis, schema)


if __name__ == "__main__":
    unittest.main()
