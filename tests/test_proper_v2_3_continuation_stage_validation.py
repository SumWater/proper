from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments/proper_v2_3"
if str(EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS))

from validate_execution_state_continuation_stage_v2_3 import validate_stage


class ProperV23ContinuationStageValidationTests(unittest.TestCase):
    def test_complete_cpu_only_stage_validation_passes(self) -> None:
        result = validate_stage()
        self.assertTrue(result["passed"])
        self.assertEqual(result["scripted_trace_count"], 4)
        self.assertEqual(len(result["stage_input_sha256"]), 14)
        self.assertFalse(result["model_loaded"])
        self.assertFalse(result["gpu_used"])
        self.assertFalse(result["existing_12_pairs_rerun"])
        self.assertFalse(result["model_run_authorized"])


if __name__ == "__main__":
    unittest.main()
