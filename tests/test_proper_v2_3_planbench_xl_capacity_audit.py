from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments/proper_v2_3"
if str(EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS))

from planbench_xl_capacity_audit_v2_3 import validate_planbench_xl_audit_design


class ProperV23PlanBenchXLCapacityAuditTests(unittest.TestCase):
    def test_design_passes_but_stops_before_inventory(self) -> None:
        result = validate_planbench_xl_audit_design()
        self.assertTrue(result["passed"])
        self.assertEqual(result["disposition"], "stop_before_inventory")
        self.assertFalse(result["source_acquired"])
        self.assertIsNone(result["candidate_count"])

    def test_design_authorizes_no_model_gpu_or_confirmation(self) -> None:
        result = validate_planbench_xl_audit_design()
        self.assertFalse(result["model_loaded"])
        self.assertFalse(result["gpu_used"])
        self.assertFalse(result["model_run_authorized"])
        self.assertFalse(result["confirmatory_run_authorized"])

    def test_design_result_validates_against_closed_schema(self) -> None:
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is not installed locally")
        result = validate_planbench_xl_audit_design()
        schema = json.loads(
            (
                ROOT
                / "schemas/proper_v2_3/planbench_xl_capacity_audit_design.schema.json"
            ).read_text(encoding="utf-8")
        )
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(result)

    def test_gold_fields_are_explicitly_audit_only(self) -> None:
        config = json.loads(
            (
                ROOT
                / "configs/proper_v2_3/planbench_xl_capacity_audit_design_v2_3.json"
            ).read_text(encoding="utf-8")
        )
        fields = set(config["audit_only_fields_never_passed_to_method"])
        self.assertIn("correct_answer", fields)
        self.assertIn("golden_tool_path", fields)
        self.assertIn("benchmark_completion_label", fields)


if __name__ == "__main__":
    unittest.main()
