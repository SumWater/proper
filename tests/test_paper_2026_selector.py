from __future__ import annotations

import sys
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from failure_memory.paper_2026 import (  # noqa: E402
    SelectionAction,
    SelectorVariant,
    assert_paper_observable_payload,
    select_from_mappings,
    select_memory,
)
from failure_memory.proper_v2 import (  # noqa: E402
    ContinuationPolicy,
    MemoryPolicyCard,
    ObservableFailure,
    ProposedAction,
    RecoveryOperation,
    RetrySafety,
    RetrySafetyAssessment,
)


def target(
    *,
    evidence: tuple[str, ...] = ("missing_required_arg", "missing:query"),
    missing: tuple[str, ...] = ("query",),
    retry_safety: RetrySafety = RetrySafety.UNKNOWN,
) -> ObservableFailure:
    safety_evidence = ("public_retry_safe",) if retry_safety != RetrySafety.UNKNOWN else ()
    return ObservableFailure(
        instruction="Find the requested document.",
        tool_name="search_docs",
        failed_arguments={},
        error_code=evidence[0],
        evidence_codes=evidence,
        failed_argument_paths=(),
        missing_fields=missing,
        public_schema_fields=("query",),
        public_required_fields=("query",),
        available_tools=("get_doc", "search_docs"),
        available_capabilities=("document_retrieval",),
        satisfied_facts=(),
        violated_facts=(),
        repeated_same_call_count=1,
        retry_safety=RetrySafetyAssessment(retry_safety, safety_evidence),
    )


def card(
    experience_id: str,
    rank: int,
    operation: RecoveryOperation,
    *,
    trigger: tuple[str, ...] = (),
    repair_targets: tuple[str, ...] = (),
    proposed_tool: str | None = None,
    stop_conditions: tuple[str, ...] = (),
    source_tool: str | None = "search_docs",
) -> MemoryPolicyCard:
    proposed = ProposedAction(proposed_tool, {}) if proposed_tool else None
    return MemoryPolicyCard(
        experience_id=experience_id,
        natural_text=f"Memory {experience_id}",
        original_rank=rank,
        retrieval_score=1.0 / rank,
        trigger_evidence=trigger,
        required_preconditions=(),
        recovery_operation=operation,
        target_object=None,
        proposed_action=proposed,
        repair_targets=repair_targets,
        continuation_policy=(
            ContinuationPolicy.TERMINATE
            if operation == RecoveryOperation.STOP_AND_REPORT
            else ContinuationPolicy.CONTINUE_DIRECTLY
        ),
        success_evidence=(),
        stop_conditions=stop_conditions,
        source_tool=source_tool,
        extraction_confidence=0.95,
    )


class PaperSelectorTests(unittest.TestCase):
    def test_full_proper_replaces_contradicted_retry_with_supported_repair(self) -> None:
        decision = select_memory(
            target(),
            [
                card(
                    "rank1-retry",
                    1,
                    RecoveryOperation.RETRY_SAME_ACTION,
                    trigger=("missing_required_arg",),
                ),
                card(
                    "rank2-repair",
                    2,
                    RecoveryOperation.REPAIR_ARGUMENTS,
                    trigger=("missing_required_arg",),
                    repair_targets=("query",),
                ),
            ],
        )
        self.assertEqual(decision.action, SelectionAction.SELECT)
        self.assertEqual(decision.selected_experience_id, "rank2-repair")
        self.assertIn(
            "retry_safety_unknown",
            decision.candidate_evaluations[0].active_contradictions,
        )

    def test_no_gate_can_select_uncertain_but_contradiction_free_candidate(self) -> None:
        candidates = [
            card(
                "rank1-info",
                1,
                RecoveryOperation.REQUEST_INFORMATION,
                source_tool="other_tool",
            ),
            card(
                "rank2-fallback",
                2,
                RecoveryOperation.USE_FALLBACK,
                proposed_tool="search_docs",
            ),
        ]
        full = select_memory(target(), candidates)
        no_gate = select_memory(target(), candidates, variant=SelectorVariant.NO_GATE)
        self.assertEqual(full.action, SelectionAction.ABSTAIN)
        self.assertEqual(no_gate.action, SelectionAction.SELECT)
        self.assertEqual(no_gate.selected_experience_id, "rank2-fallback")

    def test_no_contradiction_removes_only_active_contradiction_block(self) -> None:
        current = target(
            evidence=("timeout",),
            missing=(),
            retry_safety=RetrySafety.UNSAFE,
        )
        candidates = [
            card("rank1-info", 1, RecoveryOperation.REQUEST_INFORMATION),
            card(
                "rank2-retry",
                2,
                RecoveryOperation.RETRY_SAME_ACTION,
                trigger=("timeout",),
            ),
        ]
        full = select_memory(current, candidates)
        ablated = select_memory(
            current,
            candidates,
            variant=SelectorVariant.NO_CONTRADICTION,
        )
        self.assertEqual(full.action, SelectionAction.ABSTAIN)
        self.assertEqual(ablated.action, SelectionAction.SELECT)
        retry = ablated.candidate_evaluations[1]
        self.assertIn("retry_publicly_unsafe", retry.observed_contradictions)
        self.assertEqual(retry.active_contradictions, ())

    def test_abstention_preserves_rank1_without_applicability_claim(self) -> None:
        decision = select_memory(
            target(),
            [card("rank1-info", 1, RecoveryOperation.REQUEST_INFORMATION)],
        )
        self.assertEqual(decision.action, SelectionAction.ABSTAIN)
        self.assertEqual(decision.selected_experience_id, "rank1-info")
        self.assertFalse(decision.selection_changed)

    def test_candidate_order_does_not_change_decision(self) -> None:
        candidates = [
            card("rank1-info", 1, RecoveryOperation.REQUEST_INFORMATION),
            card(
                "rank2-repair",
                2,
                RecoveryOperation.REPAIR_ARGUMENTS,
                trigger=("missing_required_arg",),
                repair_targets=("query",),
            ),
        ]
        forward = select_memory(target(), candidates).to_mapping()
        reverse = select_memory(target(), list(reversed(candidates))).to_mapping()
        self.assertEqual(forward, reverse)

    def test_candidate_ranks_must_be_contiguous(self) -> None:
        with self.assertRaisesRegex(ValueError, "contiguous"):
            select_memory(
                target(),
                [
                    card("rank1", 1, RecoveryOperation.REQUEST_INFORMATION),
                    card("rank3", 3, RecoveryOperation.REQUEST_INFORMATION),
                ],
            )

    def test_benchmark_and_prior_outcome_fields_are_rejected_recursively(self) -> None:
        for key in ("benchmark", "scenario_name", "prior_model_outcome", "gold_action"):
            with self.subTest(key=key):
                with self.assertRaisesRegex(ValueError, "forbidden paper selector input"):
                    assert_paper_observable_payload({"nested": {key: "hidden"}})

    def test_mapping_entry_point_rejects_condition_before_parsing(self) -> None:
        with self.assertRaisesRegex(ValueError, "condition"):
            select_from_mappings(
                {"schema_version": 1, "condition": "proper"},
                [],
            )

    def test_variant_string_is_normalized_and_recorded(self) -> None:
        decision = select_memory(
            target(),
            [card("rank1-info", 1, RecoveryOperation.REQUEST_INFORMATION)],
            variant="proper_no_gate",  # type: ignore[arg-type]
        )
        self.assertEqual(decision.variant, SelectorVariant.NO_GATE)
        self.assertEqual(decision.to_mapping()["variant"], "proper_no_gate")

    def test_decision_mapping_validates_against_paper_schema(self) -> None:
        try:
            import jsonschema
        except ImportError as exc:  # pragma: no cover - repository test dependency
            self.skipTest(str(exc))
        schema = json.loads(
            (ROOT / "schemas" / "paper_2026" / "paper_selection_decision.schema.json")
            .read_text(encoding="utf-8")
        )
        decision = select_memory(
            target(),
            [
                card(
                    "rank1-retry",
                    1,
                    RecoveryOperation.RETRY_SAME_ACTION,
                    trigger=("missing_required_arg",),
                ),
                card(
                    "rank2-repair",
                    2,
                    RecoveryOperation.REPAIR_ARGUMENTS,
                    trigger=("missing_required_arg",),
                    repair_targets=("query",),
                ),
            ],
        )
        jsonschema.validate(decision.to_mapping(), schema)


if __name__ == "__main__":
    unittest.main()
