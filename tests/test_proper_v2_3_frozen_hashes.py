from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FROZEN_HASHES = {
    "outputs/proper_v1/confirmatory_gate_v1/results.json":
        "6e44ef0eba2bf7efeed7163d61a621d2a1a5385b6aa507f7ce0417222d2fceb8",
    "outputs/proper_v1/confirmatory_transient_authz_v1/results.json":
        "26fd9c062a3d462f7cefd164c3d9f7bc5460b06a2bd16cd66e5b177e1c0cd276",
    "outputs/proper_v2/toolsandbox_model_pilot_v2_1/qwen_results.json":
        "3ec804cb5d8e0ba98e60d36099a525210965b6fcfe1ddf9426549b938bc3f07a",
    "outputs/proper_v2/toolsandbox_qwen_lifecycle_development_v2_2/results.json":
        "de84767fc3136e1832210d5c1692a12302f3b1551e1efbb4a7cafcc889dd83a1",
    "outputs/proper_v2/toolsandbox_continuation_development_v2_2_1/prepared_manifest.json":
        "3efcd90ee2e8b30685430326c1d1781caec15c35c6fd8ee28dfd066e13c89f21",
    "outputs/proper_v2/toolsandbox_continuation_development_v2_2_1/static_validation.json":
        "e43191d93c148f4fccd5cbdea7726f7e82f51fcc55b6626eb400a2806c52caf1",
    "configs/proper_v2/toolsandbox_qwen_continuation_development_v2_2_1.yaml":
        "e898f2d8fa0837ac817e3bece6aeb62ca7fdf5f9c50b83971629607085da6686",
    "outputs/proper_v2/toolsandbox_qwen_continuation_development_v2_2_1/results.json":
        "541f764abb25f6719f633b8189d87e3b6177825db42087725efc5d32518fc6e8",
    "outputs/proper_v2/toolsandbox_continuation_target_inventory_v2_2_1/audit.json":
        "a969e50b35671bbba3641c7a33640c7e7ca5a452a608536612546c94808a48b9",
}


class ProperV23FrozenHashTests(unittest.TestCase):
    def test_all_frozen_result_hashes_are_unchanged(self) -> None:
        mismatches = {}
        for relative, expected in FROZEN_HASHES.items():
            actual = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
            if actual != expected:
                mismatches[relative] = {"expected": expected, "actual": actual}
        self.assertEqual(mismatches, {})


if __name__ == "__main__":
    unittest.main()
