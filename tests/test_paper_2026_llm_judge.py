from __future__ import annotations

import json
import unittest

from failure_memory.paper_2026.llm_judge import (
    JudgeCandidate,
    build_judge_messages,
    decide_with_rank1_fallback,
    parse_judge_response,
)


class LlmJudgeContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = {
            "user_instruction": "Fetch a document.",
            "failed_tool_name": "get_document",
            "failed_arguments": {"document_id": "17"},
            "public_error_or_return": {"error_code": "timeout"},
            "remaining_retry_budget": {"retries_left": 1},
            "public_tool_schemas": [],
            "observable_history": [],
        }
        self.candidates = (
            JudgeCandidate("C01", "Retry once after a timeout."),
            JudgeCandidate("C02", "Stop after repeated authorization denial."),
        )

    def test_prompt_is_anonymous_and_preserves_tfidf_order(self) -> None:
        messages = build_judge_messages(self.context, self.candidates)
        payload = json.loads(messages[1]["content"])
        self.assertEqual(
            [(item["candidate_id"], item["candidate_position"]) for item in payload["candidates"]],
            [("C01", 1), ("C02", 2)],
        )
        rendered = messages[1]["content"]
        self.assertNotIn("experience_id", rendered)
        self.assertNotIn("provenance", rendered)

    def test_strict_parser_accepts_only_known_single_field_object(self) -> None:
        self.assertEqual(
            parse_judge_response('{"selected_candidate_id":"C02"}', ["C01", "C02"]),
            "C02",
        )
        invalid = (
            '{"selected_candidate_id":"C03"}',
            '{"selected_candidate_id":"C01","reason":"x"}',
            '{"selected_candidate_id":"C01","selected_candidate_id":"C02"}',
            "```json\n{\"selected_candidate_id\":\"C01\"}\n```",
        )
        for value in invalid:
            with self.subTest(value=value), self.assertRaises((ValueError, json.JSONDecodeError)):
                parse_judge_response(value, ["C01", "C02"])

    def test_invalid_output_falls_back_to_tfidf_rank1(self) -> None:
        decision = decide_with_rank1_fallback("not-json", self.candidates)
        self.assertEqual(decision.selected_candidate_id, "C01")
        self.assertFalse(decision.parse_succeeded)
        self.assertTrue(decision.fallback_used)

    def test_context_keys_are_fail_closed(self) -> None:
        incomplete = dict(self.context)
        incomplete.pop("observable_history")
        with self.assertRaises(ValueError):
            build_judge_messages(incomplete, self.candidates)


if __name__ == "__main__":
    unittest.main()
