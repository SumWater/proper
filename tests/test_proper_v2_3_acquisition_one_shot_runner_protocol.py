from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/proper_v2_3/acquisition_one_shot_runner_protocol_v2_3.json"
RUN_SCHEMA_PATH = ROOT / "schemas/proper_v2_3/real_public_branch_capture_run.schema.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AcquisitionOneShotRunnerProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load(CONFIG_PATH)

    def test_all_frozen_input_hashes_match(self) -> None:
        for item in self.config["frozen_inputs"]:
            self.assertEqual(sha256(ROOT / item["path"]), item["sha256"], item["path"])

    def test_smoke_counts_as_the_only_first_pair_attempt(self) -> None:
        execution = self.config["execution"]
        self.assertEqual(execution["capture_order"][0], "tau3-dev-01")
        self.assertEqual(len(execution["capture_order"]), 12)
        self.assertEqual(len(set(execution["capture_order"])), 12)
        self.assertTrue(execution["smoke_is_the_only_attempt_for_that_pair"])
        self.assertEqual(execution["attempts_per_pair"], 1)

    def test_failure_policy_has_no_retry_resume_or_replacement(self) -> None:
        execution = self.config["execution"]
        worker = self.config["model_worker"]
        self.assertTrue(execution["stop_entire_stage_after_first_non_captured_pair"])
        self.assertFalse(execution["resume_after_interruption"])
        self.assertFalse(execution["rerun_failed_or_interrupted_pair"])
        self.assertFalse(execution["replacement_or_resampling"])
        self.assertEqual(worker["restart_count"], 0)
        self.assertEqual(worker["invalid_output_retry_count"], 0)

    def test_partial_run_schema_preserves_early_stops(self) -> None:
        schema = load(RUN_SCHEMA_PATH)
        attempts = schema["properties"]["attempt_artifacts"]
        count = schema["properties"]["capture_attempt_count"]
        self.assertEqual(attempts["minItems"], 0)
        self.assertEqual(attempts["maxItems"], 12)
        self.assertEqual(count["minimum"], 0)
        self.assertEqual(count["maximum"], 12)
        correction = self.config["schema_correction_before_model_output"]
        self.assertFalse(correction["modify_v1_schema"])
        self.assertIn("1_to_12", correction["resolution"])

    def test_participant_environment_and_output_boundaries_are_separate(self) -> None:
        runtime = self.config["remote_runtime"]
        persistence = self.config["persistence"]
        self.assertNotEqual(runtime["project_python"], runtime["worker_python"])
        self.assertFalse(runtime["external_api_allowed"])
        self.assertFalse(runtime["external_network_allowed"])
        self.assertTrue(self.config["execution"]["fresh_environment_per_pair"])
        self.assertFalse(self.config["execution"]["shared_environment_across_pairs"])
        self.assertTrue(persistence["partial_and_failed_runs_preserved"])
        self.assertTrue(persistence["attempt_artifacts_are_content_hashed"])

    def test_execution_gates_remain_closed_until_runner_validation(self) -> None:
        gates = self.config["gates"]
        entry = self.config["future_entrypoint_contract"]
        self.assertTrue(gates["runner_implementation_authorized_after_cpu_validation"])
        for key in (
            "runner_implemented", "remote_command_authorized", "model_loading_authorized",
            "task_execution_authorized", "real_branch_capture_authorized",
            "comparison_runner_authorized", "gpu_authorized", "confirmatory_claim_authorized",
        ):
            self.assertFalse(gates[key], key)
        self.assertFalse(entry["runner_exists_at_protocol_freeze"])
        self.assertFalse(entry["command_execution_authorized_at_this_stage"])
        runner_path = ROOT / entry["runner_path"]
        if runner_path.exists():
            implementation = load(
                ROOT / "configs/proper_v2_3/acquisition_one_shot_runner_implementation_v2_3.json"
            )
            hashes = {
                item["path"]: item["sha256"]
                for item in implementation["implementation_inputs"]
            }
            self.assertEqual(sha256(runner_path), hashes[entry["runner_path"]])
        else:
            self.assertFalse(runner_path.exists())


if __name__ == "__main__":
    unittest.main()
