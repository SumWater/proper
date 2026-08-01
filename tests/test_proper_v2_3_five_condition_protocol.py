from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments" / "proper_v2_3"
if str(EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS))

from prepare_five_condition_development_v2_3 import prepare, sha256  # noqa: E402

CONFIG = ROOT / "configs" / "proper_v2_3" / "five_condition_development_v2_3.yaml"
PROMPTS = ROOT / "configs" / "proper_v2_3" / "five_condition_prompts_v2_3.json"
SCHEMA = ROOT / "schemas" / "proper_v2_3" / "five_condition_manifest.schema.json"
EFFECTS = ROOT / "configs" / "proper_v2_3" / "toolsandbox_action_effect_contracts_v2_3.json"
REMOTE_BOOTSTRAP = ROOT / "experiments" / "proper_v2_3" / "run_five_condition_preparation_remote_v2_3.py"


class FiveConditionProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG.read_text(encoding="utf-8"))
        cls.prompts = json.loads(PROMPTS.read_text(encoding="utf-8"))
        cls.effects = json.loads(EFFECTS.read_text(encoding="utf-8"))
        cls.manifest = prepare(CONFIG)

    def test_condition_order_and_count_are_frozen(self) -> None:
        self.assertEqual([item["name"] for item in self.config["conditions"]], [
            "tfidf_rank1_memory", "proper_v2_1_memory",
            "proper_lifecycle_prompt_only", "proper_lifecycle_replan_controller",
            "proper_v2_3_full_ledger_controller",
        ])
        self.assertEqual(self.config["cohort"]["total_condition_count"], 60)

    def test_all_declared_input_hashes_match(self) -> None:
        declared = [self.config["protocol"], self.config["prompts"], *self.config["frozen_inputs"]]
        self.assertTrue(all(sha256(ROOT / item["path"]) == item["sha256"] for item in declared))

    def test_preparation_adds_only_the_fifth_condition(self) -> None:
        self.assertEqual(len(self.manifest["records"]), 12)
        self.assertTrue(self.manifest["preparation_checks"]["source_four_conditions_unchanged"])
        self.assertTrue(all(len(item["conditions"]) == 5 for item in self.manifest["records"]))

    def test_proper_conditions_have_identical_initial_request(self) -> None:
        self.assertTrue(self.manifest["preparation_checks"]["proper_initial_requests_byte_identical"])
        self.assertTrue(self.manifest["preparation_checks"]["fifth_memory_matches_condition_four"])
        expected_system = self.prompts["initial_request_policy"]["system_prompt"]
        for record in self.manifest["records"]:
            for name in (
                "proper_v2_1_memory", "proper_lifecycle_prompt_only",
                "proper_lifecycle_replan_controller", "proper_v2_3_full_ledger_controller",
            ):
                messages = record["conditions"][name]["initial_request"]["messages"]
                self.assertEqual(messages[0], {"role": "system", "content": expected_system})

    def test_fifth_condition_uses_full_observable_ledger(self) -> None:
        forbidden = set(self.config["exclusions"]["forbidden_method_inputs"])
        for record in self.manifest["records"]:
            condition = record["conditions"]["proper_v2_3_full_ledger_controller"]
            intervention = condition["intervention"]
            self.assertEqual(intervention["execution_controller"], "proper_v2_3_complete_trajectory")
            self.assertTrue(intervention["complete_trajectory_ledger"])
            self.assertTrue(intervention["observable_input_only"])
            self.assertFalse(forbidden & set(condition))
        available = {
            name for record in self.manifest["records"]
            for name in record["available_tool_names"]
        }
        contracts = {item["action_name"]: item for item in self.effects["contracts"]}
        self.assertEqual(set(contracts), available)
        self.assertEqual(len(contracts), 17)
        self.assertEqual(
            contracts["send_message_with_phone_number"]["effect_class"],
            "non_idempotent_side_effect",
        )
        self.assertEqual(self.effects["unknown_action_policy"]["controller_disposition"], "stop")

    def test_budgets_and_stop_rules_are_independent_and_prespecified(self) -> None:
        budget = self.config["controller_budget"]
        self.assertTrue(budget["budgets_are_independent"])
        self.assertEqual([budget[key] for key in (
            "maximum_retries", "maximum_verifications",
            "maximum_invalid_decisions", "maximum_replans",
        )], [1, 2, 1, 2])
        self.assertEqual(self.config["stop_rules"]["duplicate_non_idempotent_side_effect"], "stop_safety_gate")
        self.assertEqual(self.config["stop_rules"]["post_failure_completion_not_strictly_better_than_condition_four"], "stop_completion_gate")

    def test_endpoints_and_authorization_boundary_are_separate(self) -> None:
        self.assertEqual(set(self.config["evaluation"]["endpoint_groups"]), {
            "selector", "lifecycle", "continuation", "completion", "safety", "cost"
        })
        boundary = self.config["boundary"]
        self.assertFalse(boundary["model_runner_implemented"])
        self.assertFalse(boundary["development_model_run_authorized"])
        self.assertFalse(boundary["confirmatory_claim_authorized"])
        source = REMOTE_BOOTSTRAP.read_text(encoding="utf-8")
        self.assertIn("CUDA_VISIBLE_DEVICES", source)
        self.assertIn("--expected-project-revision", source)
        self.assertIn("validate_five_condition_protocol_v2_3.py", source)
        self.assertNotIn("qwen_jsonl_worker", source)

    def test_manifest_validates_and_prompts_forbid_hidden_fields(self) -> None:
        import jsonschema

        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(self.manifest)
        self.assertEqual(set(self.prompts["forbidden_prompt_fields"]), {
            "scenario_name", "semantic_family", "benchmark_recoverability",
            "gold_action", "gold_label", "evaluator_outcome", "prior_model_result",
        })


if __name__ == "__main__":
    unittest.main()
