from __future__ import annotations

import importlib.util
import hashlib
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments" / "proper_v2"
sys.path.insert(0, str(EXPERIMENTS))
SCRIPT = EXPERIMENTS / "toolsandbox_qwen_continuation_development_v2_2_1.py"
SPEC = importlib.util.spec_from_file_location(
    "toolsandbox_qwen_continuation_development_v2_2_1",
    SCRIPT,
)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def complete(self, request):
        if not self.responses:
            raise AssertionError("unexpected model request")
        payload = self.responses.pop(0)
        self.requests.append(dict(request))
        return {
            "request_id": request["request_id"],
            "ok": True,
            "raw_text": json.dumps(payload, sort_keys=True),
            "usage": {
                "prompt_token_count": 100,
                "completion_token_count": 10,
            },
        }


class QwenContinuationProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = module.load_config()
        stage_path = ROOT / cls.config["frozen_inputs"][
            "scripted_continuation_config"
        ]["path"]
        cls.stage_config = module.continuation.load_config(stage_path)
        cls.manifest = module.continuation.load_manifest(cls.stage_config)

    def provider(self, responses):
        return module.ContinuationQwenProvider(
            client=FakeClient(responses),
            config=self.config,
            stage_config=self.stage_config,
        )

    def test_qwen_config_hash_chain_and_four_condition_order(self) -> None:
        for name, item in self.config["frozen_inputs"].items():
            with self.subTest(input=name):
                digest = hashlib.sha256(
                    (ROOT / item["path"]).read_bytes()
                ).hexdigest()
                self.assertEqual(digest, item["sha256"])
        self.assertEqual(
            self.config["execution"]["condition_order"],
            [
                "tfidf_rank1_memory",
                "proper_v2_1_memory",
                "proper_lifecycle_prompt_only",
                "proper_lifecycle_replan_controller",
            ],
        )

    def test_qwen_provider_contains_no_scenario_family_branch(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn('record["semantic_family"]', source)
        self.assertNotIn("find_days_till_holiday_wifi_off", source)
        self.assertNotIn(
            "send_message_with_contact_content_cellular_off",
            source,
        )
        self.assertNotIn("turn_on_location_low_battery_mode", source)

    @staticmethod
    def decide(provider, record, condition, history, index):
        return provider.decide(
            record=record,
            condition=condition,
            branch_history=history,
            prefix_history=[],
            decision_index=index,
            decisions_left=4,
            tool_calls_left=4,
        )

    def test_controller_reprompts_without_returning_blocked_repeat(self) -> None:
        record = next(
            item
            for item in self.manifest["records"]
            if item["decision_phase"] == "post_failure"
        )
        memory = record["conditions"]["proper_v2_1_memory"]["memory"]
        action = memory["proposed_action"]
        first_payload = {
            "kind": "tool",
            "tool_name": action["tool_name"],
            "arguments": action["argument_template"],
        }
        provider = self.provider(
            [
                first_payload,
                first_payload,
                {
                    "kind": "tool",
                    "tool_name": "get_wifi_status",
                    "arguments": {},
                },
            ]
        )
        first = self.decide(
            provider,
            record,
            module.CONTROLLER_CONDITION,
            [],
            1,
        )
        self.assertEqual(first["kind"], "tool")
        history = [
            {
                "tool_name": first["tool_name"],
                "arguments": first["arguments"],
                "result": None,
                "exception": None,
            }
        ]
        second = self.decide(
            provider,
            record,
            module.CONTROLLER_CONDITION,
            history,
            2,
        )
        self.assertEqual(second["kind"], "tool")
        self.assertEqual(second["tool_name"], "get_wifi_status")
        self.assertEqual(len(second["_model_attempts"]), 2)
        self.assertEqual(
            len(second["_controller"]["blocked_attempts"]),
            1,
        )
        self.assertEqual(
            second["_controller"]["blocked_attempts"][0]["review"][
                "reason_code"
            ],
            "consumed_action_repeat_replan_required",
        )

    def test_prompt_only_does_not_silently_apply_controller(self) -> None:
        record = next(
            item
            for item in self.manifest["records"]
            if item["decision_phase"] == "post_failure"
        )
        action = record["conditions"]["proper_v2_1_memory"]["memory"][
            "proposed_action"
        ]
        repeat = {
            "kind": "tool",
            "tool_name": action["tool_name"],
            "arguments": action["argument_template"],
        }
        provider = self.provider([repeat])
        history = [
            {
                "tool_name": action["tool_name"],
                "arguments": action["argument_template"],
                "result": None,
                "exception": None,
            }
        ]
        decision = self.decide(
            provider,
            record,
            "proper_lifecycle_prompt_only",
            history,
            2,
        )
        self.assertEqual(decision["kind"], "tool")
        self.assertFalse(decision["_controller"]["guard_applied"])
        self.assertEqual(decision["_lifecycle"]["status"], "consumed")

    def test_active_stop_policy_tool_is_stopped_by_controller(self) -> None:
        record = next(
            item
            for item in self.manifest["records"]
            if item["decision_phase"] == "pre_action"
        )
        unsafe = {
            "kind": "tool",
            "tool_name": record["branch_action"]["tool_name"],
            "arguments": record["branch_action"]["arguments"],
        }
        provider = self.provider([unsafe])
        decision = self.decide(
            provider,
            record,
            module.CONTROLLER_CONDITION,
            [],
            1,
        )
        self.assertEqual(decision["kind"], "stop")
        self.assertEqual(
            decision["reason_code"],
            "active_stop_policy_tool_call_blocked",
        )
        self.assertEqual(decision["_lifecycle"]["status"], "stopped")


if __name__ == "__main__":
    unittest.main()
