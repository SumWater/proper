from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments/proper_v2_3"
if str(EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS))

from tau3_model_protocol_feasibility_v2_3 import run_audit


class Tau3ModelProtocolFeasibilityTests(unittest.TestCase):
    def test_audit_preserves_negative_model_gate(self) -> None:
        result = run_audit()
        self.assertTrue(result["audit_passed"])
        self.assertFalse(result["protocol_ready"])
        self.assertEqual(result["summary"]["source_action_mapping_count"], 12)
        self.assertEqual(result["summary"]["model_ready_count"], 4)
        self.assertEqual(
            result["summary"]["model_ready_phase_counts"],
            {"post_failure": 0, "pre_action": 4},
        )
        self.assertEqual(result["disposition"], "stop_before_model_protocol")

    def test_no_model_or_evaluator_metadata_is_used(self) -> None:
        result = run_audit()
        self.assertFalse(result["method_inputs_include_evaluator_metadata"])
        self.assertFalse(result["task_executed"])
        self.assertFalse(result["model_loaded"])
        self.assertFalse(result["model_outputs_read"])
        self.assertFalse(result["gpu_used"])
        self.assertFalse(result["model_runner_implementation_authorized"])
        self.assertFalse(result["development_model_run_authorized"])

    def test_frozen_output_validates_against_closed_schema(self) -> None:
        output = json.loads(
            (ROOT / "outputs/proper_v2_3/tau3_model_protocol_feasibility/audit.json").read_text(encoding="utf-8")
        )
        schema = json.loads(
            (ROOT / "schemas/proper_v2_3/tau3_model_protocol_feasibility.schema.json").read_text(encoding="utf-8")
        )
        self.assertFalse(schema["additionalProperties"])
        try:
            import jsonschema
        except ImportError:
            return
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(output)


if __name__ == "__main__":
    unittest.main()
