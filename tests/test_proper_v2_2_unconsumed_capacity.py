from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "proper_v2"))

import toolsandbox_unconsumed_capacity_v2_2 as capacity  # noqa: E402


class ProperV22UnconsumedCapacityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = capacity.load_config()
        cls.result = capacity.prepare()

    def test_boundary_is_cpu_only_before_target_model_outputs(self) -> None:
        boundary = self.config["boundary"]
        self.assertTrue(boundary["cpu_only"])
        self.assertTrue(boundary["public_target_inputs_inspected_for_capacity"])
        self.assertFalse(boundary["target_model_outputs_read"])
        self.assertFalse(boundary["target_scenarios_played"])
        self.assertFalse(boundary["model_loaded"])
        self.assertFalse(boundary["gpu_run_authorized"])
        self.assertFalse(boundary["confirmatory_run_authorized"])

    def test_exact_two_unconsumed_targets_are_audited(self) -> None:
        self.assertTrue(self.result["audit_passed"])
        self.assertEqual(self.result["summary"]["target_count"], 2)
        self.assertTrue(self.result["audit_checks"]["no_v2_1_model_exposure"])
        self.assertTrue(
            self.result["audit_checks"]["no_exact_source_family_overlap"]
        )
        self.assertEqual(
            {item["scenario_name"] for item in self.result["records"]},
            {
                "remove_contact_by_phone_no_remove_contact_insufficient_information",
                (
                    "remove_contact_by_phone_no_remove_contact_"
                    "insufficient_information_alt"
                ),
            },
        )

    def test_rank1_and_proper_are_behaviorally_identical_safe_stops(self) -> None:
        self.assertEqual(
            self.result["summary"]["behaviorally_distinct_pair_count"],
            0,
        )
        for item in self.result["records"]:
            self.assertEqual(
                item["rank1_experience_id"],
                item["selected_experience_id"],
            )
            self.assertEqual(item["selected_operation"], "stop_and_report")
            self.assertFalse(item["selection_changed"])
            self.assertFalse(item["behaviorally_distinct"])
            self.assertTrue(item["selected_policy_safe"])

    def test_generic_stop_is_safe_but_specific_trigger_does_not_match(
        self,
    ) -> None:
        self.assertTrue(self.result["summary"]["all_selected_policies_safe"])
        self.assertFalse(
            self.result["summary"]["all_selected_specific_trigger_match"]
        )
        for item in self.result["records"]:
            self.assertFalse(item["selected_specific_trigger_match"])

    def test_lifecycle_blocks_tool_calls_but_does_not_create_effect_capacity(
        self,
    ) -> None:
        self.assertTrue(self.result["summary"]["all_lifecycle_guards_safe"])
        for item in self.result["records"]:
            self.assertEqual(item["lifecycle_initial_status"], "active")
            self.assertTrue(item["lifecycle_tool_call_blocked"])
            self.assertEqual(
                item["lifecycle_guard_reason"],
                "active_stop_policy_tool_call_blocked",
            )
        self.assertFalse(
            self.result["summary"]["development_model_output_holdout_ready"]
        )
        self.assertFalse(
            self.result["summary"]["confirmatory_capacity_ready"]
        )

    def test_next_action_forbids_model_run_on_these_targets(self) -> None:
        self.assertEqual(
            self.result["next_action"],
            "do_not_run_model_preservation_only_and_specific_trigger_mismatch",
        )
        self.assertTrue(
            self.result["interpretation_limits"][
                "confirmatory_run_not_authorized"
            ]
        )

    def test_scenario_declarations_are_tied_to_frozen_public_source(self) -> None:
        source = (
            ROOT
            / self.config["frozen_inputs"]["scenario_source"]["path"]
        ).read_text(encoding="utf-8")
        self.assertIn(
            'name="remove_contact_by_phone_no_remove_contact_'
            'insufficient_information"',
            source,
        )
        self.assertIn(
            'name="remove_contact_by_phone_no_remove_contact_'
            'insufficient_information_alt"',
            source,
        )
        self.assertIn(
            "Remove phone number +12453344098 from my contact",
            source,
        )
        self.assertIn(
            "Get him out of my contacts.",
            source,
        )


if __name__ == "__main__":
    unittest.main()
