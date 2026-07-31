from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "proper_v2"))

from toolsandbox_qwen_pilot_v2_1 import (  # noqa: E402
    load_config,
    parse_model_decision,
    summarize,
)


class ToolSandboxQwenPilotV21Tests(unittest.TestCase):
    def test_config_is_exploratory_and_frozen(self) -> None:
        config = load_config()
        self.assertTrue(
            config["boundary"]["gpu_exploratory_pilot_authorized"]
        )
        self.assertFalse(
            config["evaluation"]["confirmatory_test_authorized"]
        )
        self.assertFalse(
            config["evaluation"][
                "generalization_to_all_agent_memory_scenarios_authorized"
            ]
        )
        self.assertEqual(config["execution"]["full_pair_count"], 12)
        self.assertEqual(config["execution"]["full_condition_count"], 24)

    def test_parser_accepts_available_tool(self) -> None:
        decision, valid, error = parse_model_decision(
            '{"kind":"tool","tool_name":"set_wifi_status",'
            '"arguments":{"on":true}}',
            available_tools={"set_wifi_status"},
        )
        self.assertTrue(valid)
        self.assertIsNone(error)
        self.assertEqual(decision["tool_name"], "set_wifi_status")
        self.assertEqual(decision["arguments"], {"on": True})

    def test_parser_rejects_unavailable_tool_without_crashing_runner(self) -> None:
        decision, valid, error = parse_model_decision(
            '{"kind":"tool","tool_name":"hidden_tool","arguments":{}}',
            available_tools={"set_wifi_status"},
        )
        self.assertFalse(valid)
        self.assertIn("unavailable tool", str(error))
        self.assertEqual(decision["kind"], "stop")
        self.assertEqual(decision["reason_code"], "invalid_model_output")

    def test_parser_rejects_non_json(self) -> None:
        decision, valid, error = parse_model_decision(
            "I would call a tool.",
            available_tools={"set_wifi_status"},
        )
        self.assertFalse(valid)
        self.assertIsNotNone(error)
        self.assertEqual(decision["reason_code"], "invalid_model_output")

    def test_summary_reports_phases_separately(self) -> None:
        def condition(similarity: float, aligned: bool) -> dict:
            return {
                "decisions": [
                    {"_model": {"valid_json_decision": True}}
                ],
                "first_decision_policy_alignment": aligned,
                "evaluation": {
                    "similarity": similarity,
                    "minefield_similarity": 0.0,
                },
            }

        records = [
            {
                "decision_phase": "post_failure",
                "identical_condition_start": True,
                "conditions": {
                    "tfidf_rank1_memory": condition(0.0, False),
                    "proper_v2_1_memory": condition(1.0, True),
                },
            },
            {
                "decision_phase": "pre_action",
                "identical_condition_start": True,
                "conditions": {
                    "tfidf_rank1_memory": condition(1.0, False),
                    "proper_v2_1_memory": condition(1.0, True),
                },
            },
        ]
        result = summarize(records)
        self.assertEqual(
            result["phase_summary"]["post_failure"][
                "proper_better_pair_count"
            ],
            1,
        )
        self.assertEqual(
            result["phase_summary"]["pre_action"]["tie_pair_count"], 1
        )
        self.assertEqual(result["invalid_json_decision_count"], 0)


if __name__ == "__main__":
    unittest.main()
