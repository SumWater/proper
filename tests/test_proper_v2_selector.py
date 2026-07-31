from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from failure_memory.proper_v2 import (
    ContinuationPolicy,
    MemoryPolicyCard,
    ObservableFailure,
    ProposedAction,
    RecoveryOperation,
    RetrySafety,
    RetrySafetyAssessment,
    select_memory,
)


def target(
    *,
    evidence_codes: tuple[str, ...] = ("missing_required_arg", "missing:query"),
    missing_fields: tuple[str, ...] = ("query",),
    retry_safety: RetrySafety = RetrySafety.UNKNOWN,
    retry_evidence: tuple[str, ...] = (),
    satisfied_facts: tuple[str, ...] = (),
    violated_facts: tuple[str, ...] = (),
) -> ObservableFailure:
    return ObservableFailure(
        instruction="Search for the requested document.",
        tool_name="search_docs",
        failed_arguments={},
        error_code=evidence_codes[0] if evidence_codes else None,
        evidence_codes=evidence_codes,
        failed_argument_paths=(),
        missing_fields=missing_fields,
        public_schema_fields=("query",),
        public_required_fields=("query",),
        available_tools=("get_doc", "search_docs"),
        available_capabilities=("document_retrieval",),
        satisfied_facts=satisfied_facts,
        violated_facts=violated_facts,
        repeated_same_call_count=1,
        retry_safety=RetrySafetyAssessment(retry_safety, retry_evidence),
    )


def card(
    experience_id: str,
    rank: int,
    operation: RecoveryOperation,
    *,
    trigger: tuple[str, ...] = ("missing_required_arg",),
    repair_targets: tuple[str, ...] = (),
    required: tuple[str, ...] = (),
    proposed_tool: str | None = None,
    continuation: ContinuationPolicy = ContinuationPolicy.CONTINUE_DIRECTLY,
    stop_conditions: tuple[str, ...] = (),
    confidence: float = 0.95,
) -> MemoryPolicyCard:
    proposed = (
        ProposedAction(proposed_tool, {}) if proposed_tool is not None else None
    )
    return MemoryPolicyCard(
        experience_id=experience_id,
        natural_text=f"Memory {experience_id}",
        original_rank=rank,
        retrieval_score=1.0 / rank,
        trigger_evidence=trigger,
        required_preconditions=required,
        recovery_operation=operation,
        target_object=None,
        proposed_action=proposed,
        repair_targets=repair_targets,
        continuation_policy=continuation,
        success_evidence=(),
        stop_conditions=stop_conditions,
        source_tool="search_docs",
        extraction_confidence=confidence,
    )


class ProperV2SelectorTests(unittest.TestCase):
    def test_repairs_missing_argument_instead_of_unsafe_retry(self) -> None:
        candidates = [
            card("rank1-retry", 1, RecoveryOperation.RETRY_SAME_ACTION),
            card(
                "rank2-repair",
                2,
                RecoveryOperation.REPAIR_ARGUMENTS,
                repair_targets=("query",),
            ),
        ]
        decision = select_memory(target(), candidates)
        self.assertEqual(decision.selected_experience_id, "rank2-repair")
        self.assertTrue(decision.selection_changed)
        rank1 = decision.candidate_evaluations[0]
        self.assertIn("retry_safety_unknown", rank1.contradictions)

    def test_safe_retry_can_replace_unsupported_stop(self) -> None:
        current = target(
            evidence_codes=("timeout",),
            missing_fields=(),
            retry_safety=RetrySafety.SAFE,
            retry_evidence=("environment_contract:bounded_retry_safe",),
        )
        candidates = [
            card(
                "rank1-stop",
                1,
                RecoveryOperation.STOP_AND_REPORT,
                trigger=("timeout",),
                continuation=ContinuationPolicy.TERMINATE,
                stop_conditions=("retry_budget_exhausted",),
            ),
            card(
                "rank2-retry",
                2,
                RecoveryOperation.RETRY_SAME_ACTION,
                trigger=("timeout",),
            ),
        ]
        decision = select_memory(current, candidates)
        self.assertEqual(decision.selected_experience_id, "rank2-retry")

    def test_unknown_retry_safety_does_not_authorize_retry_intervention(self) -> None:
        candidates = [
            card(
                "rank1-stop",
                1,
                RecoveryOperation.STOP_AND_REPORT,
                continuation=ContinuationPolicy.TERMINATE,
                stop_conditions=("persistent_denial",),
            ),
            card("rank2-retry", 2, RecoveryOperation.RETRY_SAME_ACTION),
        ]
        decision = select_memory(target(), candidates)
        self.assertFalse(decision.selection_changed)
        self.assertTrue(decision.abstained)

    def test_violated_precondition_excludes_candidate(self) -> None:
        candidates = [
            card(
                "rank1-repair",
                1,
                RecoveryOperation.REPAIR_ARGUMENTS,
                repair_targets=("query",),
            ),
            card(
                "rank2-prerequisite",
                2,
                RecoveryOperation.INVOKE_PREREQUISITE,
                required=("network_available",),
                proposed_tool="get_doc",
            ),
        ]
        decision = select_memory(
            target(violated_facts=("network_available",)), candidates
        )
        second = decision.candidate_evaluations[1]
        self.assertIn("required_precondition_violated", second.contradictions)
        self.assertEqual(decision.selected_experience_id, "rank1-repair")

    def test_unavailable_proposed_tool_is_ineligible(self) -> None:
        unavailable = card(
            "rank2-switch",
            2,
            RecoveryOperation.SWITCH_TOOL,
            proposed_tool="private_search",
        )
        decision = select_memory(
            target(),
            [
                card(
                    "rank1-repair",
                    1,
                    RecoveryOperation.REPAIR_ARGUMENTS,
                    repair_targets=("query",),
                ),
                unavailable,
            ],
        )
        self.assertIn(
            "proposed_tool_unavailable",
            decision.candidate_evaluations[1].contradictions,
        )

    def test_candidate_input_order_does_not_change_decision(self) -> None:
        candidates = [
            card("rank1-retry", 1, RecoveryOperation.RETRY_SAME_ACTION),
            card(
                "rank2-repair",
                2,
                RecoveryOperation.REPAIR_ARGUMENTS,
                repair_targets=("query",),
            ),
        ]
        forward = select_memory(target(), candidates).to_mapping()
        reverse = select_memory(target(), list(reversed(candidates))).to_mapping()
        self.assertEqual(forward, reverse)

    def test_low_confidence_candidate_cannot_intervene(self) -> None:
        candidates = [
            card("rank1-retry", 1, RecoveryOperation.RETRY_SAME_ACTION),
            card(
                "rank2-repair",
                2,
                RecoveryOperation.REPAIR_ARGUMENTS,
                repair_targets=("query",),
                confidence=0.70,
            ),
        ]
        decision = select_memory(target(), candidates)
        self.assertFalse(decision.selection_changed)
        self.assertTrue(decision.abstained)


if __name__ == "__main__":
    unittest.main()
