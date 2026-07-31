from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "proper_v2"))

from toolsandbox_model_pilot_runner_validation_v2_1 import (  # noqa: E402
    holiday_dynamic_reference_diagnostic,
    load_config,
    load_manifest,
    synthetic_decision,
)


class ToolSandboxModelPilotRunnerValidationV21Tests(unittest.TestCase):
    def test_frozen_manifest_identity_and_counts(self) -> None:
        config = load_config()
        _, manifest = load_manifest(config)
        self.assertEqual(len(manifest["records"]), 12)
        self.assertEqual(
            manifest["cohort"]["phase_counts"],
            {"post_failure": 9, "pre_action": 3},
        )

    def test_validation_cannot_authorize_model_or_gpu(self) -> None:
        config = load_config()
        self.assertTrue(config["boundary"]["scripted_decisions_only"])
        self.assertFalse(config["boundary"]["model_loaded"])
        self.assertFalse(config["boundary"]["model_outputs_read"])
        self.assertFalse(config["boundary"]["gpu_run_authorized"])
        self.assertEqual(
            config["checks"]["expected_proper_similarity_by_family"][
                "find_days_till_holiday_wifi_off"
            ],
            0.8,
        )
        self.assertTrue(
            config["known_evaluator_limitation"][
                "raw_native_scores_must_be_preserved"
            ]
        )

    def test_pre_action_proper_synthetic_decision_stops(self) -> None:
        config = load_config()
        _, manifest = load_manifest(config)
        record = next(
            item
            for item in manifest["records"]
            if item["decision_phase"] == "pre_action"
        )
        decision = synthetic_decision(
            record=record,
            condition="proper_v2_1_memory",
            branch_history=[],
            prefix_history=[],
            config=config,
        )
        self.assertEqual(decision["kind"], "stop")
        self.assertEqual(decision["reason_code"], "insufficient_information")

    def test_post_failure_proper_first_decision_matches_memory_action(self) -> None:
        config = load_config()
        _, manifest = load_manifest(config)
        record = next(
            item
            for item in manifest["records"]
            if item["decision_phase"] == "post_failure"
        )
        decision = synthetic_decision(
            record=record,
            condition="proper_v2_1_memory",
            branch_history=[],
            prefix_history=[],
            config=config,
        )
        expected = record["conditions"]["proper_v2_1_memory"]["memory"][
            "proposed_action"
        ]
        self.assertEqual(decision["tool_name"], expected["tool_name"])
        self.assertEqual(decision["arguments"], expected["argument_template"])

    def test_post_failure_rank1_retry_reuses_frozen_failed_action(self) -> None:
        config = load_config()
        _, manifest = load_manifest(config)
        record = next(
            item
            for item in manifest["records"]
            if item["decision_phase"] == "post_failure"
            and item["conditions"]["tfidf_rank1_memory"]["memory"][
                "recovery_operation"
            ]
            == "retry_same_action"
        )
        decision = synthetic_decision(
            record=record,
            condition="tfidf_rank1_memory",
            branch_history=[],
            prefix_history=[],
            config=config,
        )
        self.assertEqual(decision["kind"], "tool")
        self.assertEqual(decision["tool_name"], record["branch_action"]["tool_name"])
        self.assertEqual(decision["arguments"], record["branch_action"]["arguments"])

    def test_holiday_diagnostic_requires_exact_arguments_and_final_match(
        self,
    ) -> None:
        record = {
            "semantic_family": "find_days_till_holiday_wifi_off",
            "prefix_history": [
                {
                    "tool_name": "get_current_timestamp",
                    "result": 1000.0,
                    "exception": None,
                }
            ],
            "conditions": {
                "proper_v2_1_memory": {
                    "tool_history": [
                        {
                            "tool_name": "search_holiday",
                            "result": 2000.0,
                            "exception": None,
                        },
                        {
                            "tool_name": "timestamp_diff",
                            "arguments": {
                                "timestamp_0": 1000.0,
                                "timestamp_1": 2000.0,
                            },
                            "exception": None,
                        },
                    ],
                    "evaluation": {
                        "milestone_mapping": {
                            "3": [25, 0.0],
                            "4": [26, 1.0],
                        }
                    },
                }
            },
        }
        result = holiday_dynamic_reference_diagnostic(record)
        self.assertTrue(result["reproduced"])
        self.assertTrue(result["timestamp_arguments_reuse_matched_results"])


if __name__ == "__main__":
    unittest.main()
