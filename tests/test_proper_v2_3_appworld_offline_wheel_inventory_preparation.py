from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments/proper_v2_3"
if str(EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS))

from validate_appworld_offline_wheel_inventory_preparation_v2_3 import validate


class AppWorldOfflineWheelInventoryPreparationTests(unittest.TestCase):
    def test_preparation_passes_and_authorizes_inventory_only(self) -> None:
        result = validate()
        self.assertTrue(result["passed"])
        self.assertTrue(result["remote_wheel_inventory_authorized"])
        self.assertFalse(result["source_install_authorized"])
        self.assertEqual(result["next_gate"], "retrieve_one_pinned_wheel_and_run_read_only_inventory")

    def test_no_wheel_task_model_or_gpu_was_used(self) -> None:
        result = validate()
        for key in ("wheel_downloaded", "wheel_read", "wheel_extracted", "protected_bundle_opened", "task_or_api_data_read", "model_loaded", "gpu_used"):
            self.assertFalse(result[key])

    def test_official_wheel_identity_is_exact(self) -> None:
        config = json.loads((ROOT / "configs/proper_v2_3/appworld_offline_wheel_inventory_v2_3.json").read_text(encoding="utf-8"))
        release = config["official_release_metadata"]
        self.assertEqual(release["version"], "0.1.3.post1")
        self.assertEqual(release["size_bytes"], 625317)
        self.assertEqual(release["sha256"], "db77f8003982502383a50fa2974983894bd1c54f64e2fd3f7e1540d5edd037eb")

    def test_preparation_result_matches_closed_schema_when_available(self) -> None:
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is not installed locally")
        schema = json.loads((ROOT / "schemas/proper_v2_3/appworld_offline_wheel_inventory_preparation.schema.json").read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(validate())


if __name__ == "__main__":
    unittest.main()
