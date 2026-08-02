from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments/proper_v2_3"
if str(EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS))

from tau3_execution_state_continuation_screen_v2_3 import run_screen


class ProperV23Tau3ExecutionStateContinuationTests(unittest.TestCase):
    def test_all_twelve_balanced_pairs_pass(self) -> None:
        result = run_screen()
        self.assertTrue(result["passed"])
        self.assertEqual(result["summary"]["pair_count"], 12)
        self.assertEqual(result["summary"]["scripted_progress_completion_count"], 12)
        self.assertEqual(
            result["summary"]["effect_counts"],
            {
                "idempotent_state_setting": 4,
                "non_idempotent_side_effect": 4,
                "read_only": 4,
            },
        )

    def test_screen_authorizes_protocol_design_but_not_model_run(self) -> None:
        result = run_screen()
        self.assertTrue(result["development_model_protocol_design_authorized"])
        self.assertFalse(result["development_model_run_authorized"])
        self.assertFalse(result["confirmatory_run_authorized"])
        self.assertFalse(result["model_loaded"])
        self.assertFalse(result["gpu_used"])
        self.assertEqual(result["summary"]["new_heldout_target_capacity"], 0)

    def test_frozen_output_has_closed_schema_shape(self) -> None:
        result = json.loads(
            (
                ROOT
                / "outputs/proper_v2_3/tau3_execution_state_continuation_screen/screen.json"
            ).read_text(encoding="utf-8")
        )
        schema = json.loads(
            (
                ROOT
                / "schemas/proper_v2_3/tau3_execution_state_continuation_screen.schema.json"
            ).read_text(encoding="utf-8")
        )
        self.assertFalse(schema["additionalProperties"])
        self.assertTrue(set(schema["required"]).issubset(result))
        try:
            import jsonschema
        except ImportError:
            return
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(result)


if __name__ == "__main__":
    unittest.main()
