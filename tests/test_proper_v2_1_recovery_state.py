from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from failure_memory.proper_v2 import (  # noqa: E402
    ContinuationPolicy,
    DecisionPhase,
    MemoryPolicyCard,
    ObservableFailure,
    ObservableRecoveryState,
    ProposedAction,
    RecoveryOperation,
    RetrySafety,
    RetrySafetyAssessment,
    select_memory,
)
from failure_memory.proper_v2.boundary import (  # noqa: E402
    observable_recovery_state_from_mapping,
)


SCHEMA_ROOT = ROOT / "schemas" / "proper_v2"


def card(
    experience_id: str,
    rank: int,
    operation: RecoveryOperation,
    *,
    trigger: tuple[str, ...],
    stop_conditions: tuple[str, ...] = (),
    continuation: ContinuationPolicy = ContinuationPolicy.CONTINUE_DIRECTLY,
) -> MemoryPolicyCard:
    return MemoryPolicyCard(
        experience_id=experience_id,
        natural_text=f"Memory {experience_id}",
        original_rank=rank,
        retrieval_score=1.0 / rank,
        trigger_evidence=trigger,
        required_preconditions=(),
        recovery_operation=operation,
        target_object=None,
        proposed_action=None,
        repair_targets=(),
        continuation_policy=continuation,
        success_evidence=(),
        stop_conditions=stop_conditions,
        source_tool=None,
        extraction_confidence=1.0,
    )


def pre_action_state() -> ObservableRecoveryState:
    evidence = (
        "failure_state:insufficient_information",
        "insufficient_information:missing_temporal_context",
    )
    return ObservableRecoveryState(
        phase=DecisionPhase.PRE_ACTION,
        instruction="Find reminders created yesterday.",
        action=ProposedAction("search_reminder", {}),
        error_code=None,
        evidence_codes=evidence,
        failed_argument_paths=(),
        missing_fields=(),
        public_schema_fields=(),
        public_required_fields=(),
        available_tools=("end_conversation", "search_reminder"),
        available_capabilities=("stop_and_report",),
        satisfied_facts=("current_time:unavailable",),
        violated_facts=(),
        repeated_same_call_count=0,
        retry_safety=RetrySafetyAssessment(RetrySafety.UNKNOWN),
    )


class ProperV21RecoveryStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.state_schema = json.loads(
            (
                SCHEMA_ROOT / "observable_recovery_state.schema.json"
            ).read_text(encoding="utf-8")
        )
        cls.decision_schema = json.loads(
            (
                SCHEMA_ROOT / "selection_decision_v2_1.schema.json"
            ).read_text(encoding="utf-8")
        )

    def test_pre_action_stop_replaces_retry_without_triggering_minefield(self) -> None:
        evidence = pre_action_state().evidence_codes
        decision = select_memory(
            pre_action_state(),
            [
                card(
                    "rank1-retry",
                    1,
                    RecoveryOperation.RETRY_SAME_ACTION,
                    trigger=evidence,
                ),
                card(
                    "rank2-stop",
                    2,
                    RecoveryOperation.STOP_AND_REPORT,
                    trigger=evidence,
                    stop_conditions=evidence,
                    continuation=ContinuationPolicy.TERMINATE,
                ),
            ],
        )
        self.assertEqual(decision.selected_experience_id, "rank2-stop")
        self.assertEqual(decision.method_version, "proper_v2_1_development")
        self.assertIn(
            "retry_requires_post_failure",
            decision.candidate_evaluations[0].contradictions,
        )

    def test_pre_action_request_information_is_supported(self) -> None:
        evidence = pre_action_state().evidence_codes
        decision = select_memory(
            pre_action_state(),
            [
                card(
                    "rank1-retry",
                    1,
                    RecoveryOperation.RETRY_SAME_ACTION,
                    trigger=evidence,
                ),
                card(
                    "rank2-ask",
                    2,
                    RecoveryOperation.REQUEST_INFORMATION,
                    trigger=evidence,
                ),
            ],
        )
        self.assertEqual(decision.selected_experience_id, "rank2-ask")

    def test_pre_action_contract_rejects_failure_only_fields(self) -> None:
        payload = pre_action_state().to_mapping()
        payload["error_code"] = "permission_error"
        with self.assertRaisesRegex(ValueError, "cannot contain an error_code"):
            ObservableRecoveryState.from_mapping(payload)
        payload = pre_action_state().to_mapping()
        payload["repeated_same_call_count"] = 1
        with self.assertRaisesRegex(ValueError, "must be zero"):
            ObservableRecoveryState.from_mapping(payload)

    def test_post_failure_adapter_preserves_v2_decision(self) -> None:
        old = ObservableFailure(
            instruction="Search.",
            tool_name="search_docs",
            failed_arguments={},
            error_code="missing_required_arg",
            evidence_codes=("missing_required_arg",),
            failed_argument_paths=(),
            missing_fields=("query",),
            public_schema_fields=("query",),
            public_required_fields=("query",),
            available_tools=("search_docs",),
            available_capabilities=("document_retrieval",),
            satisfied_facts=(),
            violated_facts=(),
            repeated_same_call_count=1,
            retry_safety=RetrySafetyAssessment(RetrySafety.UNKNOWN),
        )
        candidates = [
            MemoryPolicyCard(
                experience_id="repair",
                natural_text="Repair the query.",
                original_rank=1,
                retrieval_score=1.0,
                trigger_evidence=("missing_required_arg",),
                required_preconditions=(),
                recovery_operation=RecoveryOperation.REPAIR_ARGUMENTS,
                target_object="query",
                proposed_action=None,
                repair_targets=("query",),
                continuation_policy=ContinuationPolicy.VERIFY_THEN_CONTINUE,
                success_evidence=("tool_succeeds",),
                stop_conditions=(),
                source_tool="search_docs",
                extraction_confidence=1.0,
            )
        ]
        old_decision = select_memory(old, candidates)
        new_decision = select_memory(old.to_recovery_state(), candidates)
        self.assertEqual(
            old_decision.selected_experience_id,
            new_decision.selected_experience_id,
        )
        self.assertEqual(
            old_decision.candidate_evaluations,
            new_decision.candidate_evaluations,
        )
        self.assertEqual(old_decision.method_version, "proper_v2_development")
        self.assertEqual(new_decision.method_version, "proper_v2_1_development")

    def test_v2_1_payloads_validate_against_new_schemas(self) -> None:
        state = pre_action_state()
        evidence = state.evidence_codes
        decision = select_memory(
            state,
            [
                card(
                    "stop",
                    1,
                    RecoveryOperation.STOP_AND_REPORT,
                    trigger=evidence,
                    stop_conditions=evidence,
                    continuation=ContinuationPolicy.TERMINATE,
                )
            ],
        )
        jsonschema.validate(state.to_mapping(), self.state_schema)
        jsonschema.validate(decision.to_mapping(), self.decision_schema)

    def test_v2_1_boundary_rejects_hidden_metadata(self) -> None:
        payload = pre_action_state().to_mapping()
        payload["action"]["argument_template"]["solution"] = "hidden"
        with self.assertRaisesRegex(ValueError, "forbidden PROPER v2 input"):
            observable_recovery_state_from_mapping(payload)


if __name__ == "__main__":
    unittest.main()
