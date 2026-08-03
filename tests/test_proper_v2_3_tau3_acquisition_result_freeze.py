from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/proper_v2_3/tau3_acquisition_result_freeze_v2_3.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Tau3AcquisitionResultFreezeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load(CONFIG)
        self.run = ROOT / self.config["run"]["directory"]
        self.result = load(self.run / "result.json")
        self.attempts = [load(self.run / item["path"]) for item in self.result["attempt_artifacts"]]

    def test_all_returned_and_frozen_input_hashes_match(self) -> None:
        for item in self.config["run"]["artifacts"]:
            path = self.run / item["path"]
            self.assertEqual((path.stat().st_size,sha256(path)),(item["bytes"],item["sha256"]),item["path"])
        for item in self.config["frozen_inputs"]:
            self.assertEqual(sha256(ROOT / item["path"]),item["sha256"],item["path"])

    def test_preflight_passed_and_result_stopped_at_fifth_pair(self) -> None:
        preflight = load(self.run / "preflight.json")
        self.assertTrue(preflight["passed"])
        self.assertTrue(all(preflight["checks"].values()))
        expected = self.config["expected_result"]
        for key in ("status","stop_reason","capture_attempt_count","captured_branch_count","post_failure_captured_count","duplicate_non_idempotent_execution_count"):
            self.assertEqual(self.result[key],expected[key])
        self.assertEqual([item["public_state"]["status"] for item in self.attempts],["captured"]*4+["capture_failure"])

    def test_invalid_user_output_is_preserved_without_retry(self) -> None:
        fifth = self.attempts[4]
        invalid = fifth["worker_records"][-1]
        self.assertEqual(fifth["public_state"]["failure_reason"],"invalid_user_output")
        self.assertEqual(invalid["participant"],"user")
        self.assertIn("parse_error",invalid)
        with self.assertRaises(json.JSONDecodeError):
            json.loads(invalid["raw_text"])
        self.assertFalse(any(record["request_id"].startswith("attempt-06") for attempt in self.attempts for record in attempt["worker_records"]))

    def test_safety_boundary_has_no_target_or_non_idempotent_execution(self) -> None:
        fifth = self.attempts[4]["public_state"]
        self.assertEqual(fifth["target_native_execution_count"],0)
        self.assertEqual(fifth["native_tool_execution_count"],1)
        self.assertEqual(fifth["ledger"][0]["effect_class"],"read_only")
        self.assertEqual(fifth["ledger"][0]["outcome"],"failed")
        self.assertFalse(any(entry["effect_class"] == "non_idempotent_side_effect" and entry["executed"] for attempt in self.attempts for entry in attempt["public_state"]["ledger"]))

    def test_worker_record_cost_recomputation_detects_invalid_output_undercount(self) -> None:
        records = [record for attempt in self.attempts for record in attempt["worker_records"] if "usage" in record]
        audited = {"model_request_count":len(records),"prompt_tokens":sum(record["usage"]["prompt_token_count"] for record in records),"completion_tokens":sum(record["usage"]["completion_token_count"] for record in records)}
        self.assertEqual(audited,self.config["cost_audit"]["worker_record_recomputed"])
        reported = self.result["cost"]
        reported_totals = {"model_request_count":reported["agent_request_count"]+reported["user_request_count"],"prompt_tokens":reported["agent_prompt_tokens"]+reported["user_prompt_tokens"],"completion_tokens":reported["agent_completion_tokens"]+reported["user_completion_tokens"]}
        self.assertEqual(reported_totals,self.config["cost_audit"]["reported"])
        self.assertEqual({key:audited[key]-reported_totals[key] for key in audited},self.config["cost_audit"]["omitted_invalid_user_response"])

    def test_stage_and_claim_gates_stop_closed(self) -> None:
        disposition = self.config["disposition"]
        self.assertTrue(disposition["preserve_negative_result"])
        for key in ("rerun_or_resume_authorized","same_cohort_prompt_or_runner_tuning_authorized","tau3_five_condition_protocol_authorized","comparison_runner_authorized","confirmatory_claim_authorized"):
            self.assertFalse(disposition[key])
        self.assertEqual(disposition["next_gate"],"stop_tau3_acquisition_line_and_report")


if __name__ == "__main__":
    unittest.main()
