from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "experiments"
    / "proper_v2"
    / "toolsandbox_continuation_target_inventory_v2_2_1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "toolsandbox_continuation_target_inventory_v2_2_1",
    SCRIPT,
)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


class ContinuationTargetInventoryTests(unittest.TestCase):
    def test_config_is_prospective_and_non_model(self) -> None:
        config = module.load_config()
        self.assertTrue(config["boundary"]["inventory_only"])
        self.assertFalse(config["boundary"]["scenario_played"])
        self.assertFalse(config["boundary"]["model_loaded"])
        self.assertFalse(config["boundary"]["gpu_run_authorized"])
        self.assertFalse(
            config["next_gate"]["model_run_authorized_from_inventory_alone"]
        )

    def test_semantic_family_removes_all_registered_variants(self) -> None:
        self.assertEqual(
            module.semantic_family(
                "example_multiple_user_turn_alt_three_distraction_tools"
            ),
            "example",
        )
        self.assertEqual(
            module.semantic_family("example_implicit_tool_name_scrambled"),
            "example",
        )

    def test_toolsandbox_source_identity_matches_config(self) -> None:
        config = module.load_config()
        repository = ROOT / config["repository"]["local_directory"]
        count, digest = module.python_source_manifest(repository)
        self.assertEqual(
            count,
            config["repository"]["python_source_file_count"],
        )
        self.assertEqual(
            digest,
            config["repository"]["python_source_manifest_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
