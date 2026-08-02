from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from failure_memory.proper_v2 import DecisionPhase, RecoveryOperation
from failure_memory.proper_v2.v2_3 import (
    ActionExecutionLedger,
    BudgetPolicy,
    EvidenceSource,
    ObservableProgressEvidence,
    SubgoalContract,
    initial_controller_state,
    initial_progress_state,
    progress_state_from_mapping,
)


class ProperV23ExecutionStateContinuationTests(unittest.TestCase):
    def test_initial_state_activates_only_first_subgoal(self) -> None:
        state = initial_progress_state(
            trajectory_id="t",
            subgoals=(
                SubgoalContract("one", "First public step.", ("state:one",)),
                SubgoalContract("two", "Second public step.", ("state:two",)),
            ),
        )
        self.assertEqual(state.active_subgoal_id, "one")
        self.assertEqual([item.status.value for item in state.subgoals], ["active", "pending"])

    def test_progress_evidence_rejects_agent_self_report(self) -> None:
        with self.assertRaises(ValueError):
            ObservableProgressEvidence(
                EvidenceSource.AGENT_DECISION,
                ("agent_claim:complete",),
                1,
            )

    def test_progress_mapping_rejects_hidden_fields_recursively(self) -> None:
        payload = {
            "trajectory_id": "t",
            "subgoals": [
                {
                    "subgoal_id": "one",
                    "description": "Visible task step.",
                    "success_evidence_codes": ["state:one"],
                    "status": "active",
                    "gold_action": "hidden",
                }
            ],
            "active_subgoal_id": "one",
        }
        with self.assertRaises(ValueError):
            progress_state_from_mapping(payload)

    def test_progress_state_schema_validates_mapping(self) -> None:
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is not installed locally")
        state = initial_progress_state(
            trajectory_id="schema",
            subgoals=(SubgoalContract("one", "Visible step.", ("state:one",)),),
        )
        schema = json.loads(
            (ROOT / "schemas/proper_v2_3/execution_progress_state.schema.json").read_text(
                encoding="utf-8"
            )
        )
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(state.to_mapping())

    def test_progress_trajectory_must_match_ledger(self) -> None:
        from failure_memory.proper_v2.v2_3 import route_observable_progress

        state = initial_progress_state(
            trajectory_id="progress",
            subgoals=(SubgoalContract("one", "Visible step.", ("state:one",)),),
        )
        controller = initial_controller_state(
            phase=DecisionPhase.POST_FAILURE,
            selected_memory_experience_id="memory",
            memory_operation=RecoveryOperation.REQUEST_INFORMATION,
            memory_action=None,
            budget_policy=BudgetPolicy(),
        )
        with self.assertRaises(ValueError):
            route_observable_progress(
                progress_state=state,
                controller_state=controller,
                ledger=ActionExecutionLedger("different"),
                evidence=ObservableProgressEvidence(
                    EvidenceSource.PUBLIC_STATE,
                    ("state:one",),
                    1,
                ),
                stall_threshold=2,
            )

    def test_design_configuration_authorizes_no_model_run(self) -> None:
        config = json.loads(
            (
                ROOT
                / "configs/proper_v2_3/execution_state_continuation_design_v2_3.json"
            ).read_text(encoding="utf-8")
        )
        self.assertFalse(config["boundary"]["model_runner_in_scope"])
        self.assertFalse(config["boundary"]["gpu_run_authorized"])
        self.assertFalse(config["relationship_to_frozen_v2_3"]["reruns_existing_12_pairs"])


if __name__ == "__main__":
    unittest.main()
