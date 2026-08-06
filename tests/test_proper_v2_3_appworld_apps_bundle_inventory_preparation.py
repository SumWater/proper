from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/proper_v2_3/appworld_apps_bundle_inventory_implementation_v2_3.json"


class AppWorldAppsBundleInventoryPreparationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = json.loads(CONFIG.read_text(encoding="utf-8"))

    def test_remote_attempt_is_one_shot_and_external(self) -> None:
        runtime = self.config["remote_runtime"]
        self.assertEqual(runtime["attempts"], 1)
        self.assertFalse(runtime["rerun_or_resume"])
        self.assertTrue(runtime["wheel_path"].startswith("/home/amax/proper-inputs/"))

    def test_only_bundle_inventory_gate_opens(self) -> None:
        gates = self.config["gates"]
        self.assertTrue(gates["one_remote_apps_bundle_inventory_authorized_after_validation"])
        for key in ("official_appworld_install_authorized", "source_install_authorized", "static_api_inventory_authorized", "model_run_authorized", "confirmatory_claim_authorized"):
            self.assertFalse(gates[key])

    def test_tests_data_plaintext_model_and_gpu_stay_closed(self) -> None:
        self.assertTrue(all(value is False for value in self.config["boundary"].values()))


if __name__ == "__main__":
    unittest.main()
