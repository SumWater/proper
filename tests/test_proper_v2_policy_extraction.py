from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from failure_memory.proper_v2 import load_policy_cards


def card_payload(experience_id: str, original_rank: int) -> dict:
    return {
        "schema_version": 1,
        "experience_id": experience_id,
        "natural_text": "Repair the missing query.",
        "original_rank": original_rank,
        "retrieval_score": 1.0 / original_rank,
        "trigger_evidence": ["missing_required_arg"],
        "required_preconditions": [],
        "recovery_operation": "repair_arguments",
        "target_object": "query",
        "proposed_action": None,
        "repair_targets": ["query"],
        "continuation_policy": "continue_directly",
        "success_evidence": ["tool_succeeds"],
        "stop_conditions": [],
        "source_tool": "search_docs",
        "extraction_confidence": 0.99,
    }


class ProperV2PolicyExtractionTests(unittest.TestCase):
    def test_policy_loader_round_trips_frozen_cards(self) -> None:
        payloads = [card_payload("rank1", 1), card_payload("rank2", 2)]
        cards = load_policy_cards(payloads)
        self.assertEqual([card.to_mapping() for card in cards], payloads)

    def test_policy_loader_rejects_duplicate_rank(self) -> None:
        with self.assertRaisesRegex(ValueError, "ranks must be unique"):
            load_policy_cards(
                [card_payload("rank1", 1), card_payload("rank2", 1)]
            )

    def test_policy_loader_rejects_missing_rank1(self) -> None:
        with self.assertRaisesRegex(ValueError, "include Rank-1"):
            load_policy_cards([card_payload("rank2", 2)])


if __name__ == "__main__":
    unittest.main()
