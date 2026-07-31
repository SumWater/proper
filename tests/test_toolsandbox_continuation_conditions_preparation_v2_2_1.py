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
    / "toolsandbox_continuation_conditions_preparation_v2_2_1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "continuation_conditions_preparation_v2_2_1",
    SCRIPT,
)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


class ContinuationConditionPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = module.prepare_manifest()

    def test_preparation_is_ready_and_development_only(self) -> None:
        self.assertTrue(self.result["ready_for_development_runner"])
        self.assertTrue(
            self.result["boundary"]["existing_model_exposed_pairs"]
        )
        self.assertFalse(
            self.result["boundary"]["confirmatory_claim_authorized"]
        )

    def test_four_conditions_share_each_branch_start(self) -> None:
        expected = {
            "tfidf_rank1_memory",
            "proper_v2_1_memory",
            "proper_lifecycle_prompt_only",
            "proper_lifecycle_replan_controller",
        }
        for record in self.result["records"]:
            with self.subTest(pair_id=record["pair_id"]):
                self.assertEqual(set(record["conditions"]), expected)
                hashes = {
                    condition["initial_request_sha256"]
                    for condition in record["conditions"].values()
                }
                self.assertEqual(len(hashes), 2)

    def test_three_proper_conditions_share_exact_selection(self) -> None:
        for record in self.result["records"]:
            with self.subTest(pair_id=record["pair_id"]):
                conditions = record["conditions"]
                experiences = {
                    conditions[name]["experience_id"]
                    for name in (
                        "proper_v2_1_memory",
                        "proper_lifecycle_prompt_only",
                        "proper_lifecycle_replan_controller",
                    )
                }
                memories = {
                    module.sha256_text(
                        module.canonical(conditions[name]["memory"])
                    )
                    for name in (
                        "proper_v2_1_memory",
                        "proper_lifecycle_prompt_only",
                        "proper_lifecycle_replan_controller",
                    )
                }
                self.assertEqual(len(experiences), 1)
                self.assertEqual(len(memories), 1)


if __name__ == "__main__":
    unittest.main()
