from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "proper_v2"))

from qwen_jsonl_worker_v2_1 import response, validate_request  # noqa: E402
from toolsandbox_model_pilot_preparation_v2_1 import (  # noqa: E402
    cpu_dry_run,
    load_config,
)


class ToolSandboxModelPilotPreparationV21Tests(unittest.TestCase):
    def test_frozen_config_is_exploratory_and_cannot_authorize_gpu(self) -> None:
        config = load_config()
        self.assertEqual(config["cohort"]["expected_pair_count"], 12)
        self.assertEqual(
            config["cohort"]["expected_post_failure_pair_count"], 9
        )
        self.assertEqual(config["cohort"]["expected_pre_action_pair_count"], 3)
        self.assertFalse(config["boundary"]["gpu_run_authorized"])
        self.assertFalse(
            config["evaluation"]["confirmatory_test_authorized"]
        )
        self.assertEqual(
            set(config["post_failure_prefix_recipes"]),
            {
                "find_days_till_holiday_wifi_off",
                "send_message_with_contact_content_cellular_off",
                "turn_on_location_low_battery_mode",
            },
        )
        for recipe in config["post_failure_prefix_recipes"].values():
            self.assertTrue(recipe["required_exception_substring"])
            self.assertIn("tool_name", recipe["failed_action"])
            self.assertIn("arguments", recipe["failed_action"])

    def test_cpu_dry_run_uses_no_model_or_target_scenario(self) -> None:
        result = cpu_dry_run()
        self.assertTrue(result["passed"])
        self.assertEqual(result["primary_pair_count"], 12)
        self.assertEqual(
            result["phase_counts"], {"post_failure": 9, "pre_action": 3}
        )
        self.assertEqual(result["planned_initial_model_call_count"], 24)
        self.assertFalse(result["model_loaded"])
        self.assertFalse(result["model_outputs_read"])
        self.assertFalse(result["target_scenario_played"])
        self.assertTrue(result["synthetic_non_model_output"])

    def test_worker_jsonl_contract_round_trip(self) -> None:
        request = validate_request(
            {
                "request_id": "test-1",
                "messages": [
                    {"role": "system", "content": "Return JSON."},
                    {"role": "user", "content": "Continue."},
                ],
                "seed": 1,
                "max_new_tokens": 16,
            }
        )
        result = response(
            request,
            raw_text=json.dumps({"kind": "stop", "reason_code": "test"}),
            synthetic=True,
        )
        self.assertEqual(result["request_id"], "test-1")
        self.assertTrue(result["ok"])
        self.assertTrue(result["synthetic_non_model_output"])

    def test_worker_rejects_empty_message_list(self) -> None:
        with self.assertRaises(ValueError):
            validate_request(
                {
                    "request_id": "bad",
                    "messages": [],
                    "seed": 1,
                }
            )


if __name__ == "__main__":
    unittest.main()
