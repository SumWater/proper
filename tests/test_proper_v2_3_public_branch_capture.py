from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
EXPERIMENTS = ROOT / "experiments/proper_v2_3"
if str(EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS))

from scripted_public_branch_capture_traces_v2_3 import _captures, run_traces
from src.failure_memory.proper_v2.v2_3.branch_capture import PublicBranchCapture, assert_identical_starts


class PublicBranchCaptureTests(unittest.TestCase):
    def test_scripted_three_effect_classes_pass(self) -> None:
        result = run_traces()
        self.assertTrue(result["passed"])
        self.assertEqual(result["trace_count"], 3)
        self.assertTrue(result["tau3_runtime_adapter_authorized"])
        self.assertFalse(result["model_runner_authorized"])

    def test_method_view_excludes_evaluator_checkpoint(self) -> None:
        for _, capture in _captures():
            view = capture.method_view()
            self.assertNotIn("environment_checkpoint", view)
            self.assertNotIn("checkpoint_sha256", view)
            self.assertNotIn("checkpoint_applied_call_ids", view)
            self.assertEqual(capture.replay_plan()["environment_replay_history"], [])

    def test_unknown_side_effect_is_checkpointed_and_never_replayed(self) -> None:
        capture = dict(_captures())["non_idempotent_executed_unknown"]
        plan = capture.replay_plan()
        self.assertTrue(capture.native_execution_observed)
        self.assertIn(capture.guarded_call_id, capture.checkpoint_applied_call_ids)
        self.assertIn(capture.guarded_call_id, plan["skip_environment_replay_call_ids"])
        self.assertEqual(plan["environment_replay_history"], [])

    def test_unknown_receipt_without_execution_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown outcome requires"):
            PublicBranchCapture(
                public_history=(
                    {"role": "assistant", "tool_calls": [{"id": "x", "name": "send", "arguments": {}}]},
                    {"role": "tool", "tool_call_id": "x", "content": "unknown", "error": True},
                ),
                effect_class="non_idempotent_side_effect", receipt_kind="outcome_unknown",
                guarded_call_id="x", native_execution_observed=False,
                checkpoint_payload={}, checkpoint_applied_call_ids=(), controller_state={},
            )

    def test_forbidden_gold_metadata_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "forbidden evaluator metadata"):
            PublicBranchCapture(
                public_history=({"role": "user", "content": "request", "gold_action": "send"},),
                effect_class="read_only", receipt_kind="pre_action_trigger",
                guarded_call_id=None, native_execution_observed=False,
                checkpoint_payload={}, checkpoint_applied_call_ids=(), controller_state={},
            )

    def test_checkpoint_tampering_changes_start_hash(self) -> None:
        original = dict(_captures())["read_only_pre_action"]
        changed = PublicBranchCapture(
            public_history=original.public_history, effect_class=original.effect_class,
            receipt_kind=original.receipt_kind, guarded_call_id=None,
            native_execution_observed=False, checkpoint_payload={"changed": True},
            checkpoint_applied_call_ids=(), controller_state=original.controller_state,
        )
        self.assertNotEqual(
            original.replay_plan()["identical_start_sha256"],
            changed.replay_plan()["identical_start_sha256"],
        )

    def test_five_condition_start_hashes_are_identical(self) -> None:
        names = ["a", "b", "c", "d", "e"]
        for _, capture in _captures():
            starts = assert_identical_starts(capture, names)
            self.assertEqual(len(set(starts.values())), 1)

    def test_frozen_trace_output_matches_closed_schema(self) -> None:
        output = json.loads((ROOT / "outputs/proper_v2_3/public_branch_capture_design/scripted_traces.json").read_text(encoding="utf-8"))
        schema = json.loads((ROOT / "schemas/proper_v2_3/public_branch_capture_traces.schema.json").read_text(encoding="utf-8"))
        self.assertFalse(schema["additionalProperties"])
        try:
            import jsonschema
        except ImportError:
            return
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(output)


if __name__ == "__main__":
    unittest.main()
