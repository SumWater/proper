from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments/proper_v2_3"
if str(EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS))

from validate_tau3_branch_replay_native_result_v2_3 import validate


class Tau3BranchReplayNativeResultTests(unittest.TestCase):
    def test_returned_native_result_is_frozen_and_valid(self) -> None:
        result = validate()
        self.assertTrue(result["passed"])
        self.assertTrue(all(result["checks"].values()))
        self.assertEqual(result["native_execution_count"], 1)

    def test_only_public_branch_protocol_design_advances(self) -> None:
        result = validate()
        self.assertTrue(result["public_branch_capture_protocol_design_authorized"])
        self.assertFalse(result["real_branch_capture_execution_authorized"])
        self.assertFalse(result["model_runner_authorized"])
        self.assertFalse(result["model_run_authorized"])
        self.assertFalse(result["confirmatory_run_authorized"])
        self.assertFalse(result["gpu_used"])


if __name__ == "__main__":
    unittest.main()
