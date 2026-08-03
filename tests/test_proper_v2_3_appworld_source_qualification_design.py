from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments/proper_v2_3"
if str(EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS))

from validate_appworld_source_qualification_design_v2_3 import validate


class AppWorldSourceQualificationDesignTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = json.loads((ROOT / "configs/proper_v2_3/appworld_source_qualification_design_v2_3.json").read_text(encoding="utf-8"))

    def test_design_passes_but_stops_before_source_inventory(self) -> None:
        result = validate()
        self.assertTrue(result["passed"])
        self.assertFalse(result["source_acquired"])
        self.assertFalse(result["inventory_performed"])
        self.assertIsNone(result["candidate_count"])

    def test_no_task_gold_model_or_gpu_boundary(self) -> None:
        result = validate()
        for key in ("task_instruction_read", "ground_truth_read", "model_loaded", "gpu_used", "model_run_authorized", "confirmatory_run_authorized"):
            self.assertFalse(result[key])

    def test_project_unconsumed_is_not_mislabeled_model_unexposed(self) -> None:
        boundary = self.config["exposure_boundary"]
        self.assertIsNone(boundary["foundation_model_pretraining_exposure_known"])
        self.assertFalse(boundary["may_be_called_foundation_model_unexposed"])
        self.assertFalse(boundary["may_be_called_heldout_now"])

    def test_arbitrary_code_cannot_bypass_complete_ledger(self) -> None:
        interface = self.config["execution_interface"]
        self.assertFalse(interface["arbitrary_multi_api_code_block_allowed"])
        self.assertEqual(interface["agent_action_unit"], "one_named_appworld_api_call")
        self.assertTrue(interface["every_api_proposal_recorded_before_execution"])
        self.assertTrue(interface["complete_trajectory_action_execution_ledger_required"])

    def test_user_transport_change_cannot_reopen_tau3_cohort(self) -> None:
        transport = self.config["participant_transport"]
        self.assertTrue(transport["user_message_is_plain_public_text"])
        self.assertFalse(transport["user_message_requires_json_wrapper"])
        self.assertFalse(transport["same_tau3_cohort_rerun_or_replacement"])

    def test_result_matches_closed_schema_when_jsonschema_available(self) -> None:
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is not installed locally")
        schema = json.loads((ROOT / "schemas/proper_v2_3/appworld_source_qualification_design.schema.json").read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(validate())


if __name__ == "__main__":
    unittest.main()
