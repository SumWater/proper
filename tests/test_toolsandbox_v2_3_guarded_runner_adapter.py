from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "experiments" / "proper_v2", ROOT / "experiments" / "proper_v2_3"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import continuation_development_v2_2_1 as continuation
import lifecycle_development_v2_2 as lifecycle
from failure_memory.proper_v2.v2_3 import ActionEffectClass, ActionSpec
from failure_memory.proper_v2.v2_2 import EvidenceStatus
from toolsandbox_five_condition_runner_adapter_v2_3 import (
    ExecutionAwareTrajectoryGuard, PublicEffectRegistry,
)


class GuardedRunnerAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads((ROOT / "configs/proper_v2_3/guarded_runner_validation_v2_3.json").read_text(encoding="utf-8"))
        cls.manifest = json.loads((ROOT / cls.config["source_prepared_manifest"]["path"]).read_text(encoding="utf-8"))
        registry_value = json.loads((ROOT / cls.config["effect_registry"]["path"]).read_text(encoding="utf-8"))
        cls.registry = PublicEffectRegistry(registry_value)
        stage = json.loads((ROOT / cls.config["lifecycle_config"]["path"]).read_text(encoding="utf-8"))
        cls.lifecycle_policy = continuation.lifecycle_policy(stage)

    def post_record(self):
        return next(item for item in self.manifest["records"] if item["decision_phase"] == "post_failure")

    def make_guard(self, record, prefix=None):
        return ExecutionAwareTrajectoryGuard(
            record=record, config=self.config["method_config"],
            effect_registry=self.registry, prefix_history=prefix or [],
        )

    def test_registry_covers_frozen_tools_and_unknown_stops_closed(self) -> None:
        self.assertEqual(len(self.registry.records), 17)
        self.assertEqual(
            self.registry.contract("send_message_with_phone_number").effect_class,
            ActionEffectClass.NON_IDEMPOTENT_SIDE_EFFECT,
        )
        self.assertEqual(
            self.registry.contract("not_registered").effect_class,
            ActionEffectClass.UNKNOWN_EFFECT,
        )

    def test_prefix_actions_are_part_of_complete_ledger(self) -> None:
        record = self.post_record()
        prefix = [{"tool_name": "get_wifi_status", "arguments": {}, "result": False, "exception": None}]
        guard = self.make_guard(record, prefix)
        snapshot = guard.snapshot()
        self.assertEqual(snapshot["prefix_entry_count"], 1)
        self.assertEqual(snapshot["ledger"]["entries"][0]["status"], "succeeded")

    def test_successful_recovery_is_consumed_and_synchronized(self) -> None:
        record = self.post_record()
        guard = self.make_guard(record)
        proposed = record["conditions"]["proper_v2_3_full_ledger_controller"]["memory"]["proposed_action"]
        action = {"kind": "tool", "tool_name": proposed["tool_name"], "arguments": proposed["argument_template"]}
        self.assertTrue(guard.review(action, valid=True)["decision"].decision_allowed)
        history = [{"tool_name": action["tool_name"], "arguments": action["arguments"], "result": None, "exception": None}]
        _, state = lifecycle.state_from_history(record, history, self.lifecycle_policy)
        guard.sync_history(history, state)
        self.assertEqual(guard.snapshot()["state"]["lifecycle_status"], "consumed")

    def test_successful_action_repeat_is_recorded_and_blocked(self) -> None:
        record = self.post_record()
        guard = self.make_guard(record)
        proposed = record["conditions"]["proper_v2_3_full_ledger_controller"]["memory"]["proposed_action"]
        action = {"kind": "tool", "tool_name": proposed["tool_name"], "arguments": proposed["argument_template"]}
        guard.review(action, valid=True)
        history = [{"tool_name": action["tool_name"], "arguments": action["arguments"], "result": None, "exception": None}]
        _, state = lifecycle.state_from_history(record, history, self.lifecycle_policy)
        guard.sync_history(history, state)
        repeated = guard.review(action, valid=True)["decision"]
        self.assertFalse(repeated.decision_allowed)
        blocked = guard.snapshot()["ledger"]["entries"][-1]
        self.assertEqual(blocked["status"], "proposed")
        self.assertFalse(blocked["decision_allowed"])

    def test_non_idempotent_message_repeat_never_becomes_pending(self) -> None:
        record = next(
            item for item in self.manifest["records"]
            if "send_message_with_phone_number" in item["available_tool_names"]
            and item["decision_phase"] == "post_failure"
        )
        guard = self.make_guard(record)
        proposed = record["conditions"]["proper_v2_3_full_ledger_controller"]["memory"]["proposed_action"]
        recovery = {"kind": "tool", "tool_name": proposed["tool_name"], "arguments": proposed["argument_template"]}
        guard.review(recovery, valid=True)
        history = [{"tool_name": recovery["tool_name"], "arguments": recovery["arguments"], "result": None, "exception": None}]
        _, state = lifecycle.state_from_history(record, history, self.lifecycle_policy)
        guard.sync_history(history, state)
        message = {"kind": "tool", "tool_name": "send_message_with_phone_number", "arguments": {"phone_number": "+1", "content": "x"}}
        self.assertTrue(guard.review(message, valid=True)["decision"].decision_allowed)
        history.append({"tool_name": message["tool_name"], "arguments": message["arguments"], "result": None, "exception": None})
        _, state = lifecycle.state_from_history(record, history, self.lifecycle_policy)
        guard.sync_history(history, state)
        self.assertFalse(guard.review(message, valid=True)["decision"].decision_allowed)
        self.assertEqual(len(guard.runtime.pending_entry_ids), 0)

    def test_finalize_accounts_for_last_engine_execution(self) -> None:
        record = self.post_record()
        guard = self.make_guard(record)
        proposed = record["conditions"]["proper_v2_3_full_ledger_controller"]["memory"]["proposed_action"]
        action = {"kind": "tool", "tool_name": proposed["tool_name"], "arguments": proposed["argument_template"]}
        guard.review(action, valid=True)
        history = [{"tool_name": action["tool_name"], "arguments": action["arguments"], "result": None, "exception": None}]
        _, state = lifecycle.state_from_history(record, history, self.lifecycle_policy)
        snapshot, safety = guard.finalize_summary(history=history, lifecycle_state=state)
        self.assertEqual(snapshot["synchronized_history_count"], 1)
        self.assertTrue(safety["all_allowed_executions_resolved"])

    def test_verifier_mapping_is_public_and_read_only(self) -> None:
        verifier = self.registry.verification_action("set_wifi_status")
        self.assertEqual(verifier, ActionSpec("get_wifi_status", {}))
        self.assertEqual(
            self.registry.contract(verifier.tool_name).effect_class,
            ActionEffectClass.READ_ONLY,
        )
        self.assertEqual(
            self.registry.verification_evidence_status(
                original_action=ActionSpec("set_wifi_status", {"on": True}),
                verification_result=True,
            ),
            EvidenceStatus.SATISFIED,
        )
        self.assertEqual(
            self.registry.verification_evidence_status(
                original_action=ActionSpec("set_wifi_status", {"on": True}),
                verification_result=False,
            ),
            EvidenceStatus.VIOLATED,
        )

    def test_method_adapter_has_no_scenario_or_evaluator_branch(self) -> None:
        sources = "\n".join(
            (ROOT / "experiments/proper_v2_3" / name).read_text(encoding="utf-8")
            for name in (
                "toolsandbox_five_condition_runner_adapter_v2_3.py",
                "toolsandbox_five_condition_provider_v2_3.py",
            )
        )
        for token in self.config["method_source_forbidden_tokens"]:
            self.assertNotIn(token, sources)


if __name__ == "__main__":
    unittest.main()
