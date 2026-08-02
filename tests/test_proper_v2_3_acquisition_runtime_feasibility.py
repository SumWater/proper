from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments/proper_v2_3"
if str(EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS))

from validate_acquisition_runtime_feasibility_v2_3 import validate


class AcquisitionRuntimeFeasibilityTests(unittest.TestCase):
    def test_audit_passes_but_runtime_stops(self) -> None:
        result = validate()
        self.assertTrue(result["audit_passed"])
        self.assertFalse(result["runtime_ready"])
        self.assertFalse(result["acquisition_runtime_freeze_authorized"])
        self.assertFalse(result["real_branch_capture_authorized"])

    def test_missing_freezes_are_explicit(self) -> None:
        result = validate()
        self.assertEqual(len(result["missing_freezes"]), 7)
        self.assertIn("local_tau_user_simulator_message_adapter", result["missing_freezes"])
        self.assertIn("model_directory_manifest", result["missing_freezes"])
        self.assertIn("remote_read_only_model_inventory", result["missing_freezes"])

    def test_only_cpu_adapter_and_inventory_work_advances(self) -> None:
        result = validate()
        self.assertTrue(result["participant_adapter_implementation_authorized"])
        self.assertFalse(result["model_runner_authorized"])
        self.assertFalse(result["model_loaded"])
        self.assertFalse(result["task_executed"])
        self.assertFalse(result["gpu_used"])


if __name__ == "__main__":
    unittest.main()
