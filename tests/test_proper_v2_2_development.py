from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "proper_v2"))

import lifecycle_development_v2_2 as lifecycle  # noqa: E402
import qwen_jsonl_worker_v2_2 as worker  # noqa: E402
import toolsandbox_heldout_target_audit_v2_2 as heldout  # noqa: E402
from toolsandbox_qwen_lifecycle_development_v2_2 import (  # noqa: E402
    LifecycleQwenProvider,
    load_config as load_qwen_config,
)


class ProperV22DevelopmentTests(unittest.TestCase):
    def test_static_lifecycle_validation_uses_all_development_pairs(self) -> None:
        result = lifecycle.static_validation()
        self.assertTrue(result["passed"])
        self.assertEqual(result["summary"]["pair_count"], 12)
        self.assertEqual(
            result["summary"]["post_failure_consumed_count"],
            9,
        )
        self.assertEqual(result["summary"]["pre_action_stopped_count"], 3)
        self.assertEqual(
            result["summary"]["ordinary_planning_handoff_count"],
            9,
        )
        self.assertTrue(
            result["interpretation_limits"]["final_task_completion_not_tested"]
        )

    def test_consumed_development_records_remove_memory(self) -> None:
        result = lifecycle.static_validation()
        consumed = [
            item
            for item in result["records"]
            if item["final_lifecycle"]["status"] == "consumed"
        ]
        self.assertEqual(len(consumed), 9)
        self.assertTrue(
            all(
                item["final_lifecycle"]["exposure_mode"] == "removed"
                and item["final_lifecycle"]["injection_weight"] == 0.0
                and item["ordinary_planning_handoff"]
                for item in consumed
            )
        )

    def test_heldout_audit_reads_no_model_outputs_and_stops_confirmation(
        self,
    ) -> None:
        result = heldout.audit()
        self.assertTrue(result["audit_passed"])
        self.assertFalse(result["heldout_effect_validation_ready"])
        self.assertEqual(
            result["summary"]["requires_capacity_screening_count"],
            2,
        )
        self.assertEqual(
            result["next_action"],
            "screen_unconsumed_non_source_targets_without_model_outputs",
        )
        self.assertFalse(result["boundary"]["model_outputs_read"])
        self.assertFalse(result["boundary"]["confirmatory_run_authorized"])

    def test_unconsumed_screening_candidates_are_not_source_families(self) -> None:
        result = heldout.audit()
        candidates = [
            item
            for item in result["records"]
            if item["disposition"] == "requires_capacity_screening"
        ]
        self.assertEqual(len(candidates), 2)
        self.assertEqual(
            {item["semantic_family"] for item in candidates},
            {"remove_contact_by_phone_no_remove_contact_insufficient_information"},
        )
        self.assertTrue(
            all(
                not item["v2_1_model_exposed"]
                and not item["memory_source_family_overlap"]
                for item in candidates
            )
        )

    def test_dynamic_runner_contains_no_scenario_family_branch(self) -> None:
        source = (
            ROOT
            / "experiments"
            / "proper_v2"
            / "toolsandbox_lifecycle_development_v2_2.py"
        ).read_text(encoding="utf-8")
        forbidden_families = (
            "find_days_till_holiday_wifi_off",
            "send_message_with_contact_content_cellular_off",
            "turn_on_location_low_battery_mode",
        )
        self.assertTrue(all(value not in source for value in forbidden_families))

    def test_qwen_lifecycle_prompt_removes_frozen_memory_line(self) -> None:
        config = lifecycle.load_config()
        record = lifecycle.load_manifest(config)["records"][0]
        memory, state = lifecycle.state_from_history(
            record,
            [],
            lifecycle.lifecycle_policy(config),
        )
        initial = record["conditions"]["proper_v2_1_memory"][
            "initial_request"
        ]
        messages = LifecycleQwenProvider.lifecycle_messages(
            initial,
            lifecycle.lifecycle_prompt_payload(state, memory),
        )
        user = messages[-1]["content"]
        self.assertNotIn("\nRETRIEVED_MEMORY=", "\n" + user)
        self.assertIn("MEMORY_LIFECYCLE_STATE=", user)

    def test_v2_2_worker_contract_reports_token_usage(self) -> None:
        request = worker.validate_request(
            {
                "request_id": "dry",
                "messages": [{"role": "user", "content": "test"}],
                "seed": 1,
                "max_new_tokens": 2,
            }
        )
        result = worker.response(
            request,
            completion={
                "raw_text": '{"kind":"stop","reason_code":"dry"}',
                "prompt_token_count": 10,
                "completion_token_count": 2,
            },
            synthetic=True,
        )
        self.assertEqual(result["usage"]["prompt_token_count"], 10)
        self.assertEqual(result["usage"]["completion_token_count"], 2)

    def test_qwen_development_config_hash_chain_is_frozen(self) -> None:
        config = load_qwen_config()
        self.assertTrue(config["boundary"]["gpu_development_run_authorized"])
        self.assertFalse(config["boundary"]["confirmatory_claim_authorized"])
        self.assertFalse(config["boundary"]["heldout_claim_authorized"])
        self.assertEqual(config["execution"]["pair_count"], 12)


if __name__ == "__main__":
    unittest.main()
