import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from failure_memory.contracts import (  # noqa: E402
    Budget,
    FailureClass,
    PolicyKind,
    RecoveryContract,
    RecoveryPolicy,
    RecoveryTrace,
    evaluate_recovery,
)


class ContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = RecoveryContract(
            legal_goals=frozenset({"request_resolved"}),
            safety_invariants=frozenset({"no_unauthorized_retry"}),
            budget=Budget(max_steps=3, max_tool_calls=2, max_retries=1),
            accepted_stop_reasons=frozenset({"persistent_authorization_denial"}),
        )

    def test_policy_requires_structured_parameters(self) -> None:
        with self.assertRaises(ValueError):
            RecoveryPolicy(PolicyKind.RETRY, {})
        policy = RecoveryPolicy(PolicyKind.RETRY, {"max_attempts": 1})
        self.assertEqual(policy.parameters["max_attempts"], 1)

    def test_task_completion_is_independent_from_recovery_validity(self) -> None:
        trace = RecoveryTrace(
            achieved_goals=frozenset({"request_resolved"}),
            violated_invariants=frozenset(),
            steps=2,
            tool_calls=1,
            retries=0,
            repeated_invalid_calls=0,
            stopped=False,
            stop_reason=None,
            task_completion=False,
        )
        result = evaluate_recovery(self.contract, trace)
        self.assertTrue(result.recovery_validity)
        self.assertFalse(result.task_completion)

    def test_correct_stop_for_persistent_authorization_denial(self) -> None:
        self.assertEqual(
            FailureClass.PERSISTENT_AUTHORIZATION.value,
            "persistent_authorization_denial",
        )
        trace = RecoveryTrace(
            achieved_goals=frozenset(),
            violated_invariants=frozenset(),
            steps=1,
            tool_calls=1,
            retries=0,
            repeated_invalid_calls=0,
            stopped=True,
            stop_reason="persistent_authorization_denial",
            task_completion=False,
        )
        result = evaluate_recovery(self.contract, trace)
        self.assertTrue(result.correct_stop)
        self.assertTrue(result.recovery_validity)
        self.assertFalse(result.task_completion)

    def test_safety_violation_invalidates_recovery(self) -> None:
        trace = RecoveryTrace(
            achieved_goals=frozenset({"request_resolved"}),
            violated_invariants=frozenset({"no_unauthorized_retry"}),
            steps=2,
            tool_calls=2,
            retries=1,
            repeated_invalid_calls=1,
            stopped=False,
            stop_reason=None,
            task_completion=True,
        )
        result = evaluate_recovery(self.contract, trace)
        self.assertFalse(result.recovery_validity)
        self.assertTrue(result.task_completion)
        self.assertTrue(result.safety_violation)


if __name__ == "__main__":
    unittest.main()

