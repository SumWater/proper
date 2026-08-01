from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/proper_v2_3/toolsandbox_qwen_five_condition_development_v2_3.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class QwenFiveConditionRunnerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG.read_text(encoding="utf-8"))

    def test_every_frozen_input_hash_matches(self) -> None:
        for item in self.config["frozen_inputs"]:
            self.assertEqual(sha256(ROOT / item["path"]), item["sha256"], item["role"])

    def test_five_condition_order_and_counts_are_frozen(self) -> None:
        self.assertEqual(
            [item["name"] for item in self.config["conditions"]],
            ["tfidf_rank1_memory", "proper_v2_1_memory", "proper_lifecycle_prompt_only",
             "proper_lifecycle_replan_controller", "proper_v2_3_full_ledger_controller"],
        )
        self.assertEqual(self.config["execution"]["pair_count"], 12)
        self.assertEqual(self.config["execution"]["condition_count"], 60)

    def test_model_prompt_and_independent_budgets_are_frozen(self) -> None:
        self.assertFalse(self.config["model"]["do_sample"])
        self.assertFalse(self.config["model"]["enable_thinking"])
        self.assertTrue(self.config["model"]["local_files_only"])
        self.assertEqual(set(self.config["controller_budget"]), {
            "maximum_retries", "maximum_verifications",
            "maximum_invalid_decisions", "maximum_replans",
        })

    def test_remote_launcher_runs_cpu_preflight_before_gpu_runner(self) -> None:
        source = (ROOT / "experiments/proper_v2_3/run_qwen_five_condition_remote_v2_3.py").read_text(encoding="utf-8")
        self.assertLess(source.index('"-m", "unittest"'), source.index("str(RUNNER)"))
        self.assertIn('"CUDA_VISIBLE_DEVICES": "-1"', source)
        self.assertIn('environment["CUDA_VISIBLE_DEVICES"] = "0"', source)

    def test_stop_rules_preserve_safety_completion_and_integrity(self) -> None:
        self.assertEqual(set(self.config["stop_rules"]), {
            "duplicate_non_idempotent_side_effect",
            "post_failure_completion_not_strictly_better_than_condition_four",
            "integrity_or_accounting_failure", "smoke_failure",
        })

    def test_boundary_is_development_only_and_forbids_retuning(self) -> None:
        boundary = self.config["boundary"]
        self.assertTrue(boundary["existing_model_exposed_pairs"])
        self.assertTrue(boundary["development_only"])
        self.assertFalse(boundary["confirmatory_claim_authorized"])
        self.assertFalse(boundary["heldout_claim_authorized"])
        self.assertFalse(boundary["protocol_tuning_after_output_authorized"])


if __name__ == "__main__":
    unittest.main()
