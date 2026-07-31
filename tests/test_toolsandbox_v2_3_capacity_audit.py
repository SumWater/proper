from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments" / "proper_v2_3"
if str(EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS))

from target_capacity_audit_v2_3 import validate_capacity_design


class ToolSandboxV23CapacityAuditTests(unittest.TestCase):
    def test_capacity_design_retains_frozen_zero_candidate_result(self) -> None:
        result = validate_capacity_design()
        self.assertTrue(result["passed"])
        self.assertFalse(result["new_target_capacity_available"])
        self.assertEqual(result["disposition"], "stop_no_target_capacity")

    def test_capacity_design_authorizes_no_model_or_confirmation(self) -> None:
        result = validate_capacity_design()
        self.assertFalse(result["development_model_run_authorized"])
        self.assertFalse(result["confirmatory_run_authorized"])
        self.assertEqual(result["candidate_source_count"], 0)


if __name__ == "__main__":
    unittest.main()
