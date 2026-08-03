from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/proper_v2_3/appworld_wheel_inventory_result_freeze_v2_3.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


class AppWorldWheelInventoryResultFreezeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load(CONFIG)
        self.result = load(ROOT / self.config["run"]["path"])

    def test_remote_result_and_frozen_input_hashes_match(self) -> None:
        run = self.config["run"]
        path = ROOT / run["path"]
        self.assertEqual((path.stat().st_size, sha256(path)), (run["bytes"], run["sha256"]))
        for item in self.config["frozen_inputs"]:
            self.assertEqual(sha256(ROOT / item["path"]), item["sha256"], item["path"])

    def test_all_remote_checks_passed_and_identity_matches(self) -> None:
        self.assertTrue(self.result["passed"])
        self.assertIsNone(self.result["stop_reason"])
        self.assertTrue(all(self.result["checks"].values()))
        expected = self.config["expected_inventory"]
        for key in ("wheel_filename", "wheel_size_bytes", "wheel_sha256", "distribution", "version", "member_count", "total_uncompressed_bytes", "member_manifest_sha256"):
            self.assertEqual(self.result["inventory"][key], expected[key])

    def test_member_manifest_paths_counts_and_totals_recompute(self) -> None:
        inventory = self.result["inventory"]
        members = inventory["members"]
        paths = [item["relative_path"] for item in members]
        self.assertEqual(paths, sorted(paths))
        self.assertEqual(len(paths), len(set(paths)))
        self.assertFalse(any(PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts or "\\" in path for path in paths))
        self.assertEqual(len(members), inventory["member_count"])
        self.assertEqual(sum(item["uncompressed_bytes"] for item in members), inventory["total_uncompressed_bytes"])
        self.assertEqual(canonical_sha256(members), inventory["member_manifest_sha256"])

    def test_two_encrypted_bundles_match_exact_records(self) -> None:
        members = {item["relative_path"]: item for item in self.result["inventory"]["members"]}
        expected = self.config["expected_inventory"]["bundles"]
        self.assertEqual(self.result["inventory"]["bundle_paths"], [item["path"] for item in expected])
        for item in expected:
            self.assertEqual(members[item["path"]]["uncompressed_bytes"], item["uncompressed_bytes"])
            self.assertEqual(members[item["path"]]["sha256"], item["sha256"])

    def test_no_install_task_model_or_claim_boundary_was_crossed(self) -> None:
        for key in ("wheel_extracted", "protected_bundle_opened", "appworld_imported", "task_or_api_data_read", "model_loaded", "gpu_used"):
            self.assertFalse(self.result[key])
        disposition = self.config["disposition"]
        self.assertTrue(disposition["controlled_install_protocol_design_authorized"])
        for key in ("wheel_inventory_rerun_authorized", "source_install_authorized", "protected_material_decryption_authorized", "data_download_authorized", "task_or_api_inventory_authorized", "model_run_authorized", "confirmatory_claim_authorized"):
            self.assertFalse(disposition[key])


if __name__ == "__main__":
    unittest.main()
