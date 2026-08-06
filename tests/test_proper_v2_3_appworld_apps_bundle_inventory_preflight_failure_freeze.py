from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/proper_v2_3/appworld_apps_bundle_inventory_preflight_failure_freeze_v2_3.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AppWorldAppsBundleInventoryPreflightFailureFreezeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load(CONFIG)
        run = self.config["failed_run"]
        self.result = load(ROOT / run["result_path"])

    def test_returned_result_and_frozen_inputs_have_exact_hashes(self) -> None:
        run = self.config["failed_run"]
        self.assertEqual(sha256(ROOT / run["result_path"]), run["result_sha256"])
        for item in self.config["frozen_inputs"]:
            self.assertEqual(sha256(ROOT / item["path"]), item["sha256"], item["path"])

    def test_failure_is_dependency_preflight_only(self) -> None:
        failed = [key for key, value in self.result["checks"].items() if not value]
        self.assertEqual(failed, self.config["failure_classification"]["failed_checks"])
        self.assertEqual(self.result["stop_reason"], "preflight_failed")
        self.assertIsNone(self.result["inventory"])

    def test_decryption_task_model_and_gpu_boundaries_remain_closed(self) -> None:
        boundary = self.config["observed_boundary"]
        self.assertFalse(any(boundary.values()))
        for key, expected in boundary.items():
            self.assertEqual(self.result[key], expected, key)

    def test_revision_and_scientific_inputs_were_valid(self) -> None:
        run = self.config["failed_run"]
        self.assertEqual(self.result["project_revision"], run["project_revision"])
        self.assertEqual(self.result["expected_project_revision"], run["project_revision"])
        for key in ("all_frozen_input_hashes_match", "project_revision_matches", "tracked_worktree_clean", "wheel_is_outside_tracked_project", "wheel_path_is_absolute", "zero_network_extract_model_boundary_closed"):
            self.assertTrue(self.result["checks"][key], key)

    def test_retry_stays_closed_pending_separate_dependency_protocol(self) -> None:
        gate = self.config["repair_gate"]
        self.assertTrue(gate["require_separate_dependency_provisioning_protocol"])
        self.assertTrue(gate["require_offline_or_hash_pinned_artifact"])
        self.assertFalse(gate["retry_authorized_now"])
        self.assertFalse(gate["method_prompt_budget_model_task_or_endpoint_change_allowed"])
        self.assertFalse(self.config["claims"]["heldout"])
        self.assertFalse(self.config["claims"]["confirmatory"])


if __name__ == "__main__":
    unittest.main()
