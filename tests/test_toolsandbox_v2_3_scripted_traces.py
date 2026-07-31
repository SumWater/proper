from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments" / "proper_v2_3"
if str(EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS))

from scripted_traces_v2_3 import run_scripted_traces


class ToolSandboxV23ScriptedTraceTests(unittest.TestCase):
    def test_all_scripted_multi_step_traces_pass(self) -> None:
        result = run_scripted_traces()
        self.assertTrue(result["passed"])
        self.assertEqual(result["trace_count"], 5)
        self.assertEqual(result["passed_trace_count"], 5)
        self.assertFalse(result["model_loaded"])
        self.assertFalse(result["gpu_used"])

    def test_duplicate_message_regression_executes_message_once(self) -> None:
        result = run_scripted_traces()
        record = next(
            item
            for item in result["traces"]
            if item["trace_id"] == "duplicate_message_blocked"
        )
        self.assertEqual(record["executed_message_count"], 1)

    def test_controller_has_no_scenario_or_tool_name_branch(self) -> None:
        source = (
            ROOT / "src/failure_memory/proper_v2/v2_3/controller.py"
        ).read_text(encoding="utf-8")
        for forbidden in (
            "scenario_name",
            "semantic_family",
            "send_message",
            "set_connectivity",
            "toolsandbox",
            "gold_action",
            "recoverability",
            "evaluator_outcome",
        ):
            self.assertNotIn(forbidden, source.lower())


if __name__ == "__main__":
    unittest.main()
