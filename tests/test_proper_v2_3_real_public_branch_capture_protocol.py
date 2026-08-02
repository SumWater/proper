from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments/proper_v2_3"
if str(EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS))

from validate_real_public_branch_capture_protocol_v2_3 import validate


class RealPublicBranchCaptureProtocolTests(unittest.TestCase):
    def test_protocol_design_passes_without_authorizing_capture(self) -> None:
        result = validate()
        self.assertTrue(result["passed"])
        self.assertTrue(result["capture_runtime_freeze_authorized"])
        self.assertFalse(result["real_branch_capture_execution_authorized"])
        self.assertFalse(result["model_protocol_authorized"])
        self.assertFalse(result["model_runner_authorized"])

    def test_balanced_development_partition_and_registry(self) -> None:
        result = validate()
        self.assertEqual(result["candidate_count"], 12)
        self.assertEqual(result["phase_counts"], {"post_failure": 8, "pre_action": 4})
        self.assertEqual(result["effect_counts"], {
            "idempotent_state_setting": 4,
            "non_idempotent_side_effect": 4,
            "read_only": 4,
        })
        self.assertTrue(result["checks"]["registry_covers_all_guarded_tools"])
        self.assertTrue(result["checks"]["all_declared_verifiers_are_public_read_only"])

    def test_failure_and_unknown_injection_semantics_are_distinct(self) -> None:
        config = json.loads((ROOT / "configs/proper_v2_3/real_public_branch_capture_protocol_v2_3.json").read_text(encoding="utf-8"))
        setting = config["injection"]["idempotent_state_setting"]
        side_effect = config["injection"]["non_idempotent_side_effect"]
        self.assertEqual(setting["native_execution"], "suppressed")
        self.assertEqual(setting["receipt"]["outcome"], "failed")
        self.assertEqual(side_effect["native_execution"], "exactly_once")
        self.assertEqual(side_effect["receipt"]["outcome"], "unknown")
        self.assertFalse(side_effect["native_result_exposed_to_participants"])


if __name__ == "__main__":
    unittest.main()
