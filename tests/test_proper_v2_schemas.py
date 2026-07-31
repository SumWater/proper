from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import jsonschema

from failure_memory.proper_v2 import (
    ContinuationPolicy,
    MemoryPolicyCard,
    ObservableFailure,
    RecoveryOperation,
    RetrySafety,
    RetrySafetyAssessment,
    select_memory,
)


SCHEMA_ROOT = ROOT / "schemas" / "proper_v2"


class ProperV2SchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas = {
            name: json.loads((SCHEMA_ROOT / name).read_text(encoding="utf-8"))
            for name in (
                "observable_failure.schema.json",
                "memory_policy_card.schema.json",
                "selection_decision.schema.json",
            )
        }

    def test_contract_payloads_validate_against_frozen_schemas(self) -> None:
        target = ObservableFailure(
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
        cards = [
            MemoryPolicyCard(
                experience_id="rank1",
                natural_text="Repair the missing query.",
                original_rank=1,
                retrieval_score=1.0,
                trigger_evidence=("missing_required_arg",),
                required_preconditions=(),
                recovery_operation=RecoveryOperation.REPAIR_ARGUMENTS,
                target_object="query",
                proposed_action=None,
                repair_targets=("query",),
                continuation_policy=ContinuationPolicy.CONTINUE_DIRECTLY,
                success_evidence=("tool_succeeds",),
                stop_conditions=(),
                source_tool="search_docs",
                extraction_confidence=0.99,
            )
        ]
        decision = select_memory(target, cards)
        jsonschema.validate(target.to_mapping(), self.schemas["observable_failure.schema.json"])
        jsonschema.validate(
            cards[0].to_mapping(), self.schemas["memory_policy_card.schema.json"]
        )
        jsonschema.validate(
            decision.to_mapping(), self.schemas["selection_decision.schema.json"]
        )

    def test_selection_schema_rejects_unexplained_extra_fields(self) -> None:
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(
                {
                    "schema_version": 1,
                    "method_version": "proper_v2_development",
                    "rank1_experience_id": "rank1",
                    "selected_experience_id": "rank1",
                    "selected_original_rank": 1,
                    "selection_changed": False,
                    "abstained": False,
                    "reason_codes": ["preserve"],
                    "minimum_extraction_confidence": 0.75,
                    "candidate_evaluations": [],
                    "recovery_validity": True
                },
                self.schemas["selection_decision.schema.json"],
            )


if __name__ == "__main__":
    unittest.main()
