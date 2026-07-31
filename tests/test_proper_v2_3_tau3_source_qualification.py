from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments" / "proper_v2_3"
if str(EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS))

from tau3_source_qualification_v2_3 import qualify_source

SOURCE = ROOT / "external" / "tau2-bench"
CONFIG = ROOT / "configs" / "proper_v2_3" / "tau3_source_qualification_v2_3.yaml"
SCHEMA = ROOT / "schemas" / "proper_v2_3" / "source_qualification.schema.json"


@unittest.skipUnless(SOURCE.is_dir(), "pinned tau3-bench checkout is not present")
class Tau3SourceQualificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = qualify_source()

    def test_pinned_source_qualifies_only_for_cpu_branch_screening(self) -> None:
        self.assertTrue(self.result["passed"])
        self.assertTrue(self.result["source_qualified_for_cpu_branch_screening"])
        self.assertEqual(self.result["disposition"], "continue_cpu_branch_screening")
        self.assertEqual(
            self.result["next_gate"], "cpu_scripted_recoverable_branch_validation"
        )
        self.assertEqual(len(self.result["pending_exclusion_audits"]), 3)

    def test_no_target_or_model_authority_is_created(self) -> None:
        self.assertFalse(self.result["new_target_capacity_available"])
        self.assertEqual(self.result["native_recoverable_pair_count"], 0)
        self.assertFalse(self.result["development_model_run_authorized"])
        self.assertFalse(self.result["confirmatory_run_authorized"])
        self.assertTrue(all(value is False for value in (
            self.result["boundary"]["model_loaded"],
            self.result["boundary"]["model_outputs_read"],
            self.result["boundary"]["bundled_historical_results_read"],
            self.result["boundary"]["target_tasks_executed"],
            self.result["boundary"]["gpu_used"],
            self.result["boundary"]["audit_metadata_passed_to_method"],
        )))

    def test_static_source_has_required_effect_diversity(self) -> None:
        self.assertEqual(
            self.result["static_continuation_opportunity_count"], 455
        )
        self.assertEqual(
            self.result["static_continuation_opportunities"],
            {
                "read_only": 374,
                "idempotent_state_setting": 19,
                "non_idempotent_side_effect": 62,
            },
        )
        self.assertTrue(all(self.result["capacity_checks"].values()))

    def test_partition_is_prospective_and_immutable(self) -> None:
        partition = self.result["prospective_partition"]
        self.assertEqual(partition["development_task_count"], 178)
        self.assertEqual(partition["heldout_task_count"], 54)
        self.assertEqual(partition["preservation_task_count"], 46)
        self.assertTrue(partition["labels_are_prospective_not_qualified_targets"])
        self.assertEqual(
            partition["manifest_sha256"],
            "2f5e2177b6d0ed12d4965e51f35ffdc42bf3408f833ae3229c5b1e5a8ab5e244",
        )

    def test_config_selects_no_trajectory_or_result_path(self) -> None:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        selected = [item["path"] for item in config["selected_inputs"]]
        for forbidden in config["forbidden_source_paths"]:
            self.assertFalse(
                any(
                    path == forbidden or path.startswith(forbidden + "/")
                    for path in selected
                )
            )
        forbidden_handoff = config["task_field_policy"]["forbidden_method_handoff"]
        self.assertIn("evaluation_criteria", forbidden_handoff)
        self.assertIn("gold_action", forbidden_handoff)
        self.assertIn("evaluator_outcome", forbidden_handoff)
        self.assertEqual(
            config["next_gate"]["required_exclusion_audits"],
            self.result["pending_exclusion_audits"],
        )

    def test_result_validates_against_schema_when_jsonschema_is_available(self) -> None:
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is not installed")
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(self.result)


if __name__ == "__main__":
    unittest.main()
