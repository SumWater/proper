from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments/proper_v2_3"
if str(EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS))

from scripted_appworld_controlled_install_protocol_v2_3 import run_traces


CONFIG = ROOT / "configs/proper_v2_3/appworld_controlled_install_static_inventory_protocol_v2_3.json"


class AppWorldControlledInstallProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = json.loads(CONFIG.read_text(encoding="utf-8"))

    def test_official_destructive_or_overbroad_commands_are_forbidden(self) -> None:
        observed = self.config["official_public_install_observation"]
        self.assertFalse(observed["official_install_command_allowed"])
        self.assertFalse(observed["official_data_download_command_allowed"])
        self.assertTrue(observed["package_install_also_decrypts_tests_bundle"])
        self.assertTrue(observed["data_download_removes_existing_data_directory"])

    def test_only_exact_apps_bundle_can_reach_future_inventory(self) -> None:
        bundle = self.config["protected_apps_bundle"]
        self.assertEqual(bundle["wheel_member_path"], "appworld/.source/apps.bundle")
        self.assertEqual(bundle["encrypted_sha256"], "ba58bc5679c3573aa8f60ad6f5cda4377128a0ec569de5eef9543a77561796bb")
        self.assertTrue(bundle["tests_bundle_must_not_be_decrypted"])
        self.assertTrue(bundle["data_bundle_must_not_be_downloaded"])

    def test_decrypted_inventory_persists_no_protected_plaintext(self) -> None:
        output = self.config["privacy_and_license_output"]
        for key in ("persist_plaintext_member_paths", "persist_decrypted_member_bytes", "persist_source_snippets", "persist_api_or_app_names"):
            self.assertFalse(output[key])
        self.assertTrue(output["persist_path_sha256"])
        self.assertTrue(output["persist_content_sha256"])

    def test_static_api_inventory_remains_future_and_gold_free(self) -> None:
        future = self.config["future_static_api_inventory_contract"]
        self.assertFalse(future["authorized_in_this_stage"])
        self.assertTrue(future["tests_bundle_forbidden"])
        self.assertTrue(future["data_and_tasks_forbidden"])
        self.assertTrue(future["ground_truth_and_evaluator_forbidden"])
        self.assertTrue(future["one_api_call_per_ledger_event_required"])

    def test_six_scripted_traces_stop_closed_without_crossing_boundary(self) -> None:
        traces = run_traces()
        self.assertEqual(len(traces), 6)
        self.assertEqual(sum(item["decision"].startswith("stop") for item in traces), 5)
        self.assertFalse(any(item["decrypted"] or item["extracted"] or item["protected_plaintext_persisted"] for item in traces))


if __name__ == "__main__":
    unittest.main()
