from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from failure_memory.proper_v2 import (
    ContinuationPolicy,
    DecisionPhase,
    MemoryPolicyCard,
    ObservableRecoveryState,
    ProposedAction,
    RecoveryOperation,
    RetrySafety,
    RetrySafetyAssessment,
)
from failure_memory.proper_v2.v2_3 import (
    ActionEffectClass,
    ActionEffectContract,
    ActionSpec,
    BudgetPolicy,
    action_effect_contract_from_mapping,
    controller_state_from_selection,
    initial_controller_state,
    observable_action_from_mapping,
)


class ProperV23ContractTests(unittest.TestCase):
    def test_action_identity_is_key_order_independent(self) -> None:
        first = ActionSpec(
            "send",
            {"metadata": {"b": 2, "a": 1}, "recipients": ["a", "b"]},
        )
        second = ActionSpec(
            "send",
            {"recipients": ["a", "b"], "metadata": {"a": 1, "b": 2}},
        )
        self.assertEqual(first.identity, second.identity)
        self.assertEqual(len(first.identity), 64)

    def test_action_identity_preserves_list_order(self) -> None:
        first = ActionSpec("batch", {"items": ["a", "b"]})
        second = ActionSpec("batch", {"items": ["b", "a"]})
        self.assertNotEqual(first.identity, second.identity)

    def test_action_rejects_non_json_and_non_finite_values(self) -> None:
        with self.assertRaises(ValueError):
            ActionSpec("bad", {"value": {1, 2}})
        with self.assertRaises(ValueError):
            ActionSpec("bad", {"value": float("nan")})

    def test_known_retry_safety_requires_evidence(self) -> None:
        with self.assertRaises(ValueError):
            ActionEffectContract(
                effect_class=ActionEffectClass.READ_ONLY,
                classification_evidence=("tool_schema:read_only",),
                retry_safety=RetrySafety.SAFE,
            )

    def test_verification_requires_public_evidence(self) -> None:
        with self.assertRaises(ValueError):
            ActionEffectContract(
                effect_class=ActionEffectClass.NON_IDEMPOTENT_SIDE_EFFECT,
                classification_evidence=("tool_schema:side_effect",),
                retry_safety=RetrySafety.UNKNOWN,
                verification_supported=True,
            )

    def test_budget_classes_are_independent_in_serialized_state(self) -> None:
        state = initial_controller_state(
            phase=DecisionPhase.PRE_ACTION,
            selected_memory_experience_id="memory::test",
            memory_operation=RecoveryOperation.REQUEST_INFORMATION,
            memory_action=None,
            budget_policy=BudgetPolicy(
                maximum_retries=1,
                maximum_verifications=2,
                maximum_invalid_decisions=3,
                maximum_replans=4,
            ),
        )
        self.assertEqual(
            state.to_mapping()["budgets"],
            {
                "remaining_retries": 1,
                "remaining_verifications": 2,
                "remaining_invalid_decisions": 3,
                "remaining_replans": 4,
            },
        )

    def test_configuration_is_json_and_forbids_model_runner(self) -> None:
        config = json.loads(
            (ROOT / "configs/proper_v2_3/execution_controller_v2_3.yaml").read_text(
                encoding="utf-8"
            )
        )
        self.assertFalse(config["boundary"]["gpu_run_authorized"])
        self.assertFalse(config["boundary"]["model_runner_in_scope"])
        self.assertFalse(
            config["unified_interface"]["scenario_specific_branches_allowed"]
        )

    def test_v2_3_boundary_rejects_hidden_fields_recursively(self) -> None:
        for forbidden in (
            "recoverability",
            "gold_action",
            "evaluator_outcome",
            "scenario_name",
            "semantic_family",
            "prior_model_result",
        ):
            with self.subTest(forbidden=forbidden), self.assertRaises(ValueError):
                observable_action_from_mapping(
                    {
                        "tool_name": "lookup",
                        "arguments": {"nested": {forbidden: "hidden"}},
                    }
                )
        contract = action_effect_contract_from_mapping(
            {
                "effect_class": "read_only",
                "classification_evidence": ["tool_schema:read_only"],
                "retry_safety": "unknown",
            }
        )
        self.assertEqual(contract.effect_class, ActionEffectClass.READ_ONLY)

    def test_effect_contract_mapping_requires_a_real_boolean(self) -> None:
        with self.assertRaises(ValueError):
            action_effect_contract_from_mapping(
                {
                    "effect_class": "read_only",
                    "classification_evidence": ["tool_schema:read_only"],
                    "retry_safety": "unknown",
                    "verification_supported": "false",
                }
            )

    def test_same_selection_adapter_handles_both_decision_phases(self) -> None:
        card = MemoryPolicyCard(
            experience_id="memory::stop",
            natural_text="Ask for missing information and stop.",
            original_rank=1,
            retrieval_score=1.0,
            trigger_evidence=("insufficient_information",),
            required_preconditions=(),
            recovery_operation=RecoveryOperation.STOP_AND_REPORT,
            target_object=None,
            proposed_action=None,
            repair_targets=(),
            continuation_policy=ContinuationPolicy.TERMINATE,
            success_evidence=("agent_stopped",),
            stop_conditions=("insufficient_information",),
            source_tool=None,
            extraction_confidence=1.0,
        )
        for phase in (DecisionPhase.PRE_ACTION, DecisionPhase.POST_FAILURE):
            action = (
                None
                if phase == DecisionPhase.PRE_ACTION
                else ProposedAction("lookup", {"id": "x"})
            )
            observable = ObservableRecoveryState(
                phase=phase,
                instruction="Handle the visible state.",
                action=action,
                error_code=None if phase == DecisionPhase.PRE_ACTION else "failed",
                evidence_codes=("insufficient_information",),
                failed_argument_paths=(),
                missing_fields=(),
                public_schema_fields=("id",),
                public_required_fields=("id",),
                available_tools=("lookup",),
                available_capabilities=(),
                satisfied_facts=(),
                violated_facts=(),
                repeated_same_call_count=(
                    0 if phase == DecisionPhase.PRE_ACTION else 1
                ),
                retry_safety=RetrySafetyAssessment(RetrySafety.UNKNOWN),
            )
            state = controller_state_from_selection(
                observable_state=observable,
                selected_memory=card,
                budget_policy=BudgetPolicy(),
            )
            self.assertEqual(state.phase, phase)


if __name__ == "__main__":
    unittest.main()
