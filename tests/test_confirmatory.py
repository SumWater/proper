from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from failure_memory.confirmatory import (  # noqa: E402
    aggregate_pair_indicators,
    argument_diff,
    behavior_atoms,
    canonicalize_decision,
    exact_mcnemar_two_sided,
    pair_indicators,
)
from failure_memory.utilization import AgentDecision, DecisionKind  # noqa: E402


class ConfirmatoryTests(unittest.TestCase):
    def test_canonicalization_ignores_argument_key_order(self) -> None:
        left = AgentDecision(DecisionKind.TOOL, "update", {"b": 2, "a": 1})
        right = AgentDecision(DecisionKind.TOOL, "update", {"a": 1, "b": 2})
        self.assertEqual(canonicalize_decision(left), canonicalize_decision(right))

    def test_argument_diff_detects_empty_container_addition(self) -> None:
        diff = argument_diff({}, {"fields": {}})
        self.assertEqual(diff.added, ("/fields",))
        self.assertEqual(diff.removed, ())

    def test_behavior_atoms_capture_partial_retry_without_exact_retry(self) -> None:
        baseline = AgentDecision(DecisionKind.TOOL, "create", {"fields": {"id": "a"}})
        memory = AgentDecision(DecisionKind.TOOL, "create", {"fields": {}})
        atoms = behavior_atoms(
            failed_action={"tool_name": "create", "args": {}},
            no_memory_decision=baseline,
            condition_decision=memory,
        )
        self.assertTrue(atoms["same_tool"])
        self.assertFalse(atoms["exact_retry"])
        self.assertEqual(atoms["argument_add"], ["/fields"])
        self.assertTrue(atoms["different_from_no_memory"])

    def test_pair_indicators_separate_harm_from_strict_adoption(self) -> None:
        baseline = AgentDecision(DecisionKind.TOOL, "create", {"fields": {"id": "a"}})
        memory = AgentDecision(DecisionKind.TOOL, "create", {"fields": {}})
        result = pair_indicators(
            no_memory_recovery_validity=True,
            memory_recovery_validity=False,
            no_memory_decision=baseline,
            memory_decision=memory,
            strict_policy_adoption=False,
        )
        self.assertTrue(result.paired_negative_transfer)
        self.assertTrue(result.memory_induced_action_change)
        self.assertTrue(result.inapplicable_memory_harm)
        self.assertFalse(result.policy_followed_harm)

    def test_exact_mcnemar_is_two_sided(self) -> None:
        self.assertEqual(exact_mcnemar_two_sided(0, 0), 1.0)
        self.assertEqual(exact_mcnemar_two_sided(5, 0), 0.0625)
        self.assertEqual(exact_mcnemar_two_sided(6, 0), 0.03125)

    def test_aggregate_uses_recovery_validity_as_primary_endpoint(self) -> None:
        baseline_decision = AgentDecision(DecisionKind.TOOL, "t", {"x": 1})
        memory_decision = AgentDecision(DecisionKind.TOOL, "t", {"x": 2})
        no_memory = [True] * 6
        memory = [False] * 6
        indicators = [
            pair_indicators(
                no_memory_recovery_validity=True,
                memory_recovery_validity=False,
                no_memory_decision=baseline_decision,
                memory_decision=memory_decision,
                strict_policy_adoption=False,
            )
            for _ in range(6)
        ]
        aggregate = aggregate_pair_indicators(indicators, no_memory, memory)
        self.assertEqual(aggregate["paired_negative_transfer_count"], 6)
        self.assertEqual(aggregate["paired_positive_transfer_count"], 0)
        self.assertEqual(aggregate["net_paired_effect"], -1.0)
        self.assertTrue(aggregate["directional_hypothesis_supported"])


if __name__ == "__main__":
    unittest.main()
