from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.failure_memory.proper_v2.v2_3.branch_capture import PublicBranchCapture
from src.failure_memory.proper_v2.v2_3.branch_replay_adapter import (
    BranchReplayIntegrityError,
    SplitStateEnvironmentAdapter,
)


class FakeEnvironment:
    def __init__(self) -> None:
        self.state = {}
        self.replayed_mutations = 0
        self.received_history = None

    def set_state(self, initialization_data, initialization_actions, message_history, strict=True):
        self.state = dict(initialization_data)
        self.received_history = list(message_history)
        self.replayed_mutations += len(message_history)

    def export(self):
        return dict(self.state)

    def get_domain_name(self):
        return "fake"


def unknown_capture() -> PublicBranchCapture:
    return PublicBranchCapture(
        public_history=(
            {"role": "user", "content": "send once"},
            {"role": "assistant", "tool_calls": [{"id": "effect-1", "name": "send", "arguments": {"body": "x"}}]},
            {"role": "tool", "tool_call_id": "effect-1", "content": {"code": "result_unknown"}, "error": True},
        ),
        effect_class="non_idempotent_side_effect", receipt_kind="outcome_unknown",
        guarded_call_id="effect-1", native_execution_observed=True,
        checkpoint_payload={"sent": ["x"]}, checkpoint_applied_call_ids=("effect-1",),
        controller_state={"ledger": [{"call_id": "effect-1", "outcome": "unknown"}]},
    )


class Tau3BranchReplayAdapterTests(unittest.TestCase):
    def make_adapter(self):
        environment = FakeEnvironment()
        capture = unknown_capture()
        adapter = SplitStateEnvironmentAdapter(
            environment, capture.replay_plan(), checkpoint_exporter=lambda env: env.export()
        )
        return capture, environment, adapter

    def test_checkpoint_restores_without_replaying_side_effect(self) -> None:
        capture, environment, adapter = self.make_adapter()
        adapter.set_state(None, None, list(capture.public_history))
        self.assertTrue(adapter.initialized)
        self.assertEqual(environment.state, {"sent": ["x"]})
        self.assertEqual(environment.received_history, [])
        self.assertEqual(environment.replayed_mutations, 0)

    def test_adapter_delegates_environment_api(self) -> None:
        _, _, adapter = self.make_adapter()
        self.assertEqual(adapter.get_domain_name(), "fake")

    def test_tampered_public_history_is_rejected(self) -> None:
        capture, _, adapter = self.make_adapter()
        history = list(capture.public_history)
        history[0] = {"role": "user", "content": "changed"}
        with self.assertRaisesRegex(BranchReplayIntegrityError, "participant history"):
            adapter.set_state(None, None, history)

    def test_task_initialization_merge_is_rejected(self) -> None:
        capture, _, adapter = self.make_adapter()
        with self.assertRaisesRegex(BranchReplayIntegrityError, "cannot be merged"):
            adapter.set_state({"hidden": True}, None, list(capture.public_history))

    def test_second_initialization_is_rejected(self) -> None:
        capture, _, adapter = self.make_adapter()
        adapter.set_state(None, None, list(capture.public_history))
        with self.assertRaisesRegex(BranchReplayIntegrityError, "only be initialized once"):
            adapter.set_state(None, None, list(capture.public_history))

    def test_checkpoint_digest_mismatch_is_rejected_at_construction(self) -> None:
        plan = unknown_capture().replay_plan()
        plan["environment_initialization"] = {"sent": []}
        with self.assertRaisesRegex(BranchReplayIntegrityError, "checkpoint payload"):
            SplitStateEnvironmentAdapter(FakeEnvironment(), plan)

    def test_restored_checkpoint_mismatch_is_rejected(self) -> None:
        capture = unknown_capture()
        environment = FakeEnvironment()
        adapter = SplitStateEnvironmentAdapter(
            environment, capture.replay_plan(), checkpoint_exporter=lambda _: {"sent": []}
        )
        with self.assertRaisesRegex(BranchReplayIntegrityError, "restored environment"):
            adapter.set_state(None, None, list(capture.public_history))


if __name__ == "__main__":
    unittest.main()
