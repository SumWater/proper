from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from failure_memory.contracts import PolicyKind, RecoveryPolicy  # noqa: E402
from failure_memory.utilization import (  # noqa: E402
    AgentDecision,
    DecisionKind,
    RunOutcome,
    behavior_matches_policy,
    compare_paired_outcomes,
)


class UtilizationTests(unittest.TestCase):
    def test_retry_match_requires_exact_failed_action(self) -> None:
        policy = RecoveryPolicy(PolicyKind.RETRY, {"max_attempts": 1})
        failed = {"tool_name": "update", "args": {"id": "a"}}
        exact = AgentDecision(DecisionKind.TOOL, "update", {"id": "a"})
        revised = AgentDecision(DecisionKind.TOOL, "update", {"id": "b"})
        self.assertTrue(behavior_matches_policy(policy, failed_action=failed, decision=exact))
        self.assertFalse(behavior_matches_policy(policy, failed_action=failed, decision=revised))

    def test_structured_stop_requires_matching_reason(self) -> None:
        policy = RecoveryPolicy(
            PolicyKind.STOP_AND_REPORT,
            {"reason_code": "persistent_authorization_denial"},
        )
        correct = AgentDecision(
            DecisionKind.STOP,
            reason_code="persistent_authorization_denial",
        )
        wrong = AgentDecision(DecisionKind.STOP, reason_code="generic_failure")
        self.assertTrue(behavior_matches_policy(policy, failed_action={}, decision=correct))
        self.assertFalse(behavior_matches_policy(policy, failed_action={}, decision=wrong))

    def test_hard_regression_is_paired_harm(self) -> None:
        baseline = RunOutcome(True, True, False, 0, 1, 1)
        memory = RunOutcome(False, False, False, 1, 1, 1)
        comparison = compare_paired_outcomes(memory, baseline)
        self.assertTrue(comparison.harmful)
        self.assertEqual(
            comparison.reasons,
            ("lost_recovery_validity", "lost_task_completion"),
        )

    def test_cost_only_harm_requires_additional_invalid_call(self) -> None:
        baseline = RunOutcome(False, False, False, 0, 1, 0)
        memory = RunOutcome(False, False, False, 1, 1, 1)
        comparison = compare_paired_outcomes(memory, baseline)
        self.assertEqual(comparison.reasons, ("additional_repeated_invalid_call",))

    def test_mixed_hard_outcomes_are_not_labeled_harm(self) -> None:
        baseline = RunOutcome(False, True, False, 0, 1, 1)
        memory = RunOutcome(True, False, False, 0, 1, 1)
        self.assertFalse(compare_paired_outcomes(memory, baseline).harmful)


if __name__ == "__main__":
    unittest.main()
