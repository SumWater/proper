from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/proper_v2_3/tau3_acquisition_preflight_failure_freeze_v2_3.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Tau3AcquisitionPreflightFailureFreezeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load(CONFIG)
        run = self.config["failed_run"]
        self.preflight = load(ROOT / run["preflight_path"])
        self.result = load(ROOT / run["result_path"])

    def test_returned_artifacts_have_exact_hashes(self) -> None:
        run = self.config["failed_run"]
        self.assertEqual(sha256(ROOT / run["preflight_path"]),run["preflight_sha256"])
        self.assertEqual(sha256(ROOT / run["result_path"]),run["result_sha256"])
        for item in self.config["frozen_inputs"]:
            self.assertEqual(sha256(ROOT / item["path"]),item["sha256"],item["path"])

    def test_only_clean_worktree_check_failed(self) -> None:
        failed = [key for key, value in self.preflight["checks"].items() if not value]
        self.assertEqual(failed,["tracked_worktree_clean"])
        self.assertFalse(self.preflight["passed"])
        self.assertEqual(self.result["status"],"preflight_failed")

    def test_no_model_task_tool_or_gpu_boundary(self) -> None:
        boundary = self.result["boundary"]
        cost = self.result["cost"]
        self.assertEqual(self.result["capture_attempt_count"],0)
        self.assertEqual(self.result["attempt_artifacts"],[])
        self.assertFalse(any((boundary["model_loaded"],boundary["model_outputs_read"],boundary["task_executed"],boundary["gpu_used"])))
        for key in ("agent_request_count","user_request_count","native_tool_execution_count","agent_prompt_tokens","user_prompt_tokens"):
            self.assertEqual(cost[key],0)

    def test_retry_is_infrastructure_only_and_preserves_claim_boundaries(self) -> None:
        gate = self.config["retry_gate"]
        self.assertEqual(gate["attempt_or_model_retry_count_consumed"],0)
        self.assertTrue(gate["same_command_only"])
        self.assertTrue(gate["require_clean_tracked_worktree"])
        self.assertFalse(gate["method_prompt_budget_model_task_order_or_endpoint_change_allowed"])
        self.assertFalse(self.config["claims"]["heldout"])
        self.assertFalse(self.config["claims"]["confirmatory"])


if __name__ == "__main__":
    unittest.main()
