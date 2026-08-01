from __future__ import annotations

import json
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments" / "proper_v2_3"
if str(EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS))

from tau3_branch_screen_v2_3 import audit_candidates, audit_frozen_inputs, execution_manifest

CONFIG = ROOT / "configs" / "proper_v2_3" / "tau3_branch_screen_v2_3.yaml"
SOURCE = ROOT / "external" / "tau2-bench"
OUTPUT = ROOT / "outputs" / "proper_v2_3" / "tau3_branch_screen" / "branch_screen.json"


@unittest.skipUnless(SOURCE.is_dir(), "pinned tau3-bench checkout is not present")
class Tau3BranchScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG.read_text(encoding="utf-8"))

    def test_candidate_set_is_balanced_and_development_only(self) -> None:
        candidates = self.config["candidates"]
        self.assertEqual(len(candidates), 12)
        self.assertEqual(Counter(item["effect_class"] for item in candidates), {
            "read_only": 4, "idempotent_state_setting": 4, "non_idempotent_side_effect": 4,
        })
        self.assertEqual({item["domain"] for item in candidates}, {"airline", "retail"})
        self.assertEqual(self.config["boundary"]["candidate_partition"], "development_only")

    def test_all_candidates_are_train_members_with_continuation_depth(self) -> None:
        records = audit_candidates(SOURCE, self.config)
        self.assertTrue(all(item["source_split"] == "train" for item in records))
        self.assertTrue(all(item["name_matches"] and item["depth_passed"] for item in records))
        self.assertTrue(all(item["actions_after"] >= 2 for item in records))

    def test_execution_source_manifest_is_frozen(self) -> None:
        actual = execution_manifest(SOURCE)
        lock = self.config["source_lock"]
        self.assertEqual(actual, {"file_count": lock["execution_manifest_file_count"],
                                  "bytes": lock["execution_manifest_bytes"],
                                  "sha256": lock["execution_manifest_sha256"]})

    def test_exclusion_sources_and_hashes_are_recomputed(self) -> None:
        result = audit_frozen_inputs(self.config)
        self.assertTrue(all(item["passed"] for item in result["frozen_hash_checks"]))
        self.assertTrue(result["proper_v1_exact_match"])
        self.assertTrue(result["proper_v2_exact_match"])
        self.assertTrue(result["new_family_string_disjoint_from_v1_and_v2"])
        self.assertFalse(result["candidate_targets_used_to_tune_controller"])

    def test_method_handoff_excludes_task_and_evaluator_metadata(self) -> None:
        boundary = self.config["boundary"]
        self.assertTrue(boundary["evaluator_actions_used_only_for_offline_membership_and_depth_audit"])
        self.assertFalse(boundary["method_receives_task_id_or_evaluator_metadata"])
        self.assertFalse(boundary["target_tasks_executed"])

    def test_generated_branch_result_preserves_safety_boundaries(self) -> None:
        if not OUTPUT.is_file():
            self.skipTest("branch screen output has not been generated")
        result = json.loads(OUTPUT.read_text(encoding="utf-8"))
        self.assertTrue(result["passed"])
        self.assertEqual(result["summary"]["qualified_development_pair_count"], 12)
        self.assertEqual(result["summary"]["new_heldout_target_capacity"], 0)
        self.assertFalse(result["summary"]["development_model_run_authorized"])
        self.assertTrue(all(item["exact_repeat_blocked"] for item in result["pairs"]))
        self.assertTrue(all(item["guarded_native_execution_count"] == 1 for item in result["pairs"] if item["effect_class"] == "non_idempotent_side_effect"))


if __name__ == "__main__":
    unittest.main()
