from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ProperV23PlanBenchXLSourceQualificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = json.loads(
            (
                ROOT
                / "configs/proper_v2_3/planbench_xl_source_qualification_v2_3.json"
            ).read_text(encoding="utf-8")
        )
        self.result = json.loads(
            (
                ROOT
                / "outputs/proper_v2_3/planbench_xl_source_qualification/source_qualification.json"
            ).read_text(encoding="utf-8")
        )

    def test_frozen_source_and_all_qualification_checks_match(self) -> None:
        self.assertEqual(self.result["source_revision"], self.config["source"]["revision"])
        self.assertEqual(self.result["source_file_sha256"], self.config["frozen_files"])
        self.assertTrue(self.result["passed"])
        self.assertTrue(all(self.result["checks"].values()))

    def test_structural_pool_is_not_accepted_full_capacity(self) -> None:
        self.assertEqual(self.result["structural_continuation_pool_size"], 322)
        self.assertEqual(self.result["accepted_full_proper_v2_3_candidate_count"], 0)
        self.assertEqual(
            self.result["disposition"], "stop_full_proper_v2_3_capacity_gate"
        )

    def test_effect_coverage_exposes_decisive_limitation(self) -> None:
        self.assertEqual(
            self.result["action_effect_coverage"],
            {
                "read_only": 185,
                "idempotent_state_setting": 0,
                "non_idempotent_side_effect": 0,
                "unknown_effect": 0,
            },
        )
        self.assertIn(
            "zero_state_setting_or_non_idempotent_side_effect_coverage",
            self.result["stop_reasons"],
        )

    def test_result_authorizes_no_model_gpu_or_confirmation(self) -> None:
        self.assertFalse(self.result["model_loaded"])
        self.assertFalse(self.result["model_outputs_read"])
        self.assertFalse(self.result["gpu_used"])
        self.assertFalse(self.result["model_run_authorized"])
        self.assertFalse(self.result["confirmatory_run_authorized"])

    def test_result_has_closed_schema_shape(self) -> None:
        schema = json.loads(
            (
                ROOT
                / "schemas/proper_v2_3/planbench_xl_source_qualification.schema.json"
            ).read_text(encoding="utf-8")
        )
        self.assertFalse(schema["additionalProperties"])
        self.assertTrue(set(schema["required"]).issubset(self.result))
        try:
            import jsonschema
        except ImportError:
            return
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(self.result)


if __name__ == "__main__":
    unittest.main()
