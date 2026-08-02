from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.proper_v2_3.validate_qwen_model_inventory_result_v2_3 import inventory_shape_errors

SCHEMA = json.loads((ROOT / "schemas/proper_v2_3/qwen_model_inventory.schema.json").read_text(encoding="utf-8"))
SUCCESS = json.loads((ROOT / "outputs/proper_v2_3/qwen_model_inventory_remote/20260802T042655Z-amax-a740a864f8fe/inventory.json").read_text(encoding="utf-8"))
FAILURES = [
    json.loads(path.read_text(encoding="utf-8"))
    for path in sorted((ROOT / "outputs/proper_v2_3/qwen_model_inventory_remote").glob("20260802T042*/inventory.json"))
    if "042655" not in str(path)
]


class QwenModelInventoryResultTests(unittest.TestCase):
    def test_returned_success_has_closed_consistent_shape(self) -> None:
        self.assertEqual(inventory_shape_errors(SUCCESS, set(SCHEMA["required"])), [])

    def test_path_traversal_is_rejected(self) -> None:
        changed = copy.deepcopy(SUCCESS)
        changed["files"][0]["relative_path"] = "../outside"
        self.assertIn("unsafe_relative_path", inventory_shape_errors(changed, set(SCHEMA["required"])))

    def test_size_and_manifest_mutations_are_rejected(self) -> None:
        changed = copy.deepcopy(SUCCESS)
        changed["files"][0]["size_bytes"] += 1
        errors = inventory_shape_errors(changed, set(SCHEMA["required"]))
        self.assertIn("total_bytes_mismatch", errors)
        self.assertIn("manifest_mismatch", errors)

    def test_both_preflight_failures_are_preserved(self) -> None:
        self.assertEqual(len(FAILURES), 2)
        self.assertTrue(all(item["stop_reason"] == "preflight_failed" for item in FAILURES))
        self.assertTrue(all(item["file_count"] == 0 and not item["model_loaded"] for item in FAILURES))


if __name__ == "__main__":
    unittest.main()
