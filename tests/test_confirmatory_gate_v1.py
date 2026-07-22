from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

from confirmatory_gate_v1 import (  # noqa: E402
    aggregate_primary,
    decisions_from_result,
    load_config,
    test_file as resolve_test_file,
)
from failure_memory.confirmatory import pair_indicators  # noqa: E402
from failure_memory.utilization import AgentDecision, DecisionKind  # noqa: E402


class ConfirmatoryGateV1Tests(unittest.TestCase):
    def test_runtime_is_explicitly_post_result_refactoring(self) -> None:
        config = load_config()
        self.assertEqual(
            config["status"],
            "refactored_runtime_after_completed_formal_result",
        )
        self.assertEqual(
            config["dataset"]["sha256"],
            "12c5e1e93926f4089dfc8d0c60cea53b556057360562375510744858fc6f1161",
        )
        self.assertEqual(config["gate"]["probability_threshold"], 0.75)

    def test_original_formal_config_keeps_experiment_time_identity(self) -> None:
        path = ROOT / "configs" / "confirmatory_gate_v1.yaml"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(
            digest,
            "781f8305162840e6ce6e3ca43890255ace0bda4e3108997e2b62d92a085423f1",
        )

    def test_public_test_path_is_separate_from_dev(self) -> None:
        config = load_config()
        path = resolve_test_file(config)
        self.assertEqual(path.name, "test_public.jsonl")
        self.assertNotEqual(path.parent, ROOT / "work" / "toolmisusebench_sample")

    def test_primary_direction_is_gate_improvement(self) -> None:
        stop = AgentDecision(DecisionKind.STOP, reason_code="baseline_failure")
        tool = AgentDecision(DecisionKind.TOOL, tool_name="read_file", args={"path": "x"})
        rows = []
        for _ in range(6):
            indicator = pair_indicators(
                no_memory_recovery_validity=False,
                memory_recovery_validity=True,
                no_memory_decision=stop,
                memory_decision=tool,
                strict_policy_adoption=False,
            )
            rows.append(
                {
                    "indicator": indicator,
                    "rank1_recovery_validity": False,
                    "gate_recovery_validity": True,
                }
            )
        aggregate = aggregate_primary(rows, 0.05)
        self.assertEqual(aggregate["paired_positive_transfer_count"], 6)
        self.assertEqual(aggregate["paired_negative_transfer_count"], 0)
        self.assertTrue(aggregate["directional_hypothesis_supported"])

    def test_saved_decision_round_trip(self) -> None:
        tool = decisions_from_result(
            {"kind": "tool", "tool_name": "read_file", "args": {"path": "x"}}
        )
        stop = decisions_from_result(
            {"kind": "stop", "reason_code": "persistent_authorization_denial"}
        )
        self.assertEqual(tool.kind, DecisionKind.TOOL)
        self.assertEqual(stop.kind, DecisionKind.STOP)


if __name__ == "__main__":
    unittest.main()
