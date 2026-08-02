from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments/proper_v2_3"
if str(EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS))

from scripted_continuation_traces_v2_3 import run_scripted_continuation_traces


class ToolSandboxV23ContinuationTraceTests(unittest.TestCase):
    def test_all_continuation_traces_pass_without_model_or_gpu(self) -> None:
        result = run_scripted_continuation_traces()
        self.assertTrue(result["passed"])
        self.assertEqual(result["trace_count"], 4)
        self.assertEqual(result["passed_trace_count"], 4)
        self.assertFalse(result["model_loaded"])
        self.assertFalse(result["gpu_used"])

    def test_trace_set_covers_handoff_stall_unknown_effect_and_boundary(self) -> None:
        trace_ids = {
            item["trace_id"] for item in run_scripted_continuation_traces()["traces"]
        }
        self.assertEqual(
            trace_ids,
            {
                "continuation-handoff-completion",
                "continuation-progress-stall",
                "continuation-unknown-effect",
                "continuation-evidence-boundary",
            },
        )

    def test_continuation_controller_has_no_benchmark_specific_branch(self) -> None:
        source = (
            ROOT / "src/failure_memory/proper_v2/v2_3/continuation.py"
        ).read_text(encoding="utf-8").lower()
        for forbidden in (
            "toolsandbox",
            "planbench",
            "send_message",
            "set_connectivity",
            "gold_action",
            "evaluator_outcome",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
