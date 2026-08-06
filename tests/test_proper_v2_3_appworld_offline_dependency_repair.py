from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/proper_v2_3/appworld_offline_dependency_repair_v2_3.json"
RUNNER = ROOT / "experiments/proper_v2_3/run_appworld_offline_dependency_repair_remote_v2_3.py"


class AppWorldOfflineDependencyRepairTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = json.loads(CONFIG.read_text(encoding="utf-8"))
        self.source = RUNNER.read_text(encoding="utf-8")

    def test_exact_complete_dependency_chain_is_pinned(self) -> None:
        self.assertEqual(self.config["expected_versions"], {"cryptography":"49.0.0","cffi":"2.0.0","pycparser":"2.23"})
        self.assertEqual(len(self.config["artifacts"]), 3)
        self.assertTrue(all(len(item["sha256"]) == 64 and item["bytes"] > 0 for item in self.config["artifacts"]))

    def test_install_is_offline_binary_only_and_dependency_closed(self) -> None:
        for token in ('"--no-index"', '"--no-deps"', '"--only-binary=:all:"'):
            self.assertIn(token, self.source)
        self.assertNotIn("requests", self.source)
        self.assertNotIn("urllib", self.source)

    def test_external_absent_target_and_exact_wheelhouse_are_required(self) -> None:
        self.assertIn('"target_is_absolute_external_and_absent"', self.source)
        self.assertIn("observed_files == expected_files", self.source)

    def test_version_probe_precedes_single_inventory_invocation(self) -> None:
        self.assertLess(self.source.index("probe_code ="), self.source.index("INVENTORY_RUNNER" , self.source.index("probe_code =")))
        self.assertEqual(self.source.count("str(INVENTORY_RUNNER)"), 1)

    def test_model_gpu_network_and_plaintext_boundaries_are_closed(self) -> None:
        for token in ('"network_allowed": False','"protected_plaintext_persisted": False','"model_loaded": False','"gpu_used": False'):
            self.assertIn(token, self.source)


if __name__ == "__main__":
    unittest.main()
