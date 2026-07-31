from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments" / "proper_v2"
sys.path.insert(0, str(EXPERIMENTS))
SCRIPT = EXPERIMENTS / "toolsandbox_continuation_development_v2_2_1.py"
SPEC = importlib.util.spec_from_file_location(
    "toolsandbox_continuation_development_v2_2_1",
    SCRIPT,
)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


class ScriptedContinuationDevelopmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = module.continuation.load_config()
        cls.manifest = module.continuation.load_manifest(cls.config)
        cls.provider = module.ScriptedContinuationProvider(cls.config)

    def decide(self, record, condition, history):
        return self.provider.decide(
            record=record,
            condition=condition,
            branch_history=history,
            prefix_history=[],
            decision_index=1,
            decisions_left=4,
            tool_calls_left=4,
        )

    def test_post_failure_repeat_is_internal_replan_not_tool_execution(self) -> None:
        record = next(
            item
            for item in self.manifest["records"]
            if item["decision_phase"] == "post_failure"
        )
        first = self.decide(
            record,
            "proper_lifecycle_replan_controller",
            [],
        )
        self.assertEqual(first["kind"], "tool")
        history = [
            {
                "tool_name": first["tool_name"],
                "arguments": first["arguments"],
                "result": None,
                "exception": None,
            }
        ]
        second = self.decide(
            record,
            "proper_lifecycle_replan_controller",
            history,
        )
        self.assertEqual(second["kind"], "stop")
        self.assertEqual(
            second["_controller"]["blocked_review"]["disposition"],
            "replan",
        )
        self.assertFalse(
            second["_controller"]["blocked_review"]["decision_allowed"]
        )
        self.assertEqual(
            second["_controller"]["handoff_review"]["disposition"],
            "allow",
        )

    def test_pre_action_controller_executes_no_tool(self) -> None:
        record = next(
            item
            for item in self.manifest["records"]
            if item["decision_phase"] == "pre_action"
        )
        decision = self.decide(
            record,
            "proper_lifecycle_replan_controller",
            [],
        )
        self.assertEqual(decision["kind"], "stop")
        self.assertEqual(decision["reason_code"], "scripted_safe_stop")

    def test_persistent_conditions_are_not_played_by_scripted_provider(self) -> None:
        record = self.manifest["records"][0]
        for condition in ("tfidf_rank1_memory", "proper_v2_1_memory"):
            with self.subTest(condition=condition):
                decision = self.decide(record, condition, [])
                self.assertEqual(decision["kind"], "stop")
                self.assertEqual(
                    decision["reason_code"],
                    "persistent_condition_not_scripted",
                )


if __name__ == "__main__":
    unittest.main()
