from __future__ import annotations

import sys
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from failure_memory.candidate_selector import (  # noqa: E402
    FailureState,
    PolicyClass,
    RuleSet,
    assert_observable_payload,
    extract_candidate_features,
    extract_failure_features,
    parse_policy_from_text,
    rerank_candidates,
)


def observation(
    *,
    code: str,
    args: dict,
    missing: list[str] | None = None,
    tool: str = "update",
    required: list[str] | None = None,
    repeats: int = 1,
) -> dict:
    error = {
        "code": code,
        "message": "public failure",
        "details": {"missing": missing or [], "tool_name": tool},
    }
    call = {"tool_name": tool, "args": args, "output": None, "error": error}
    return {
        "instruction": "perform the task",
        "tool_schemas": [
            {
                "name": tool,
                "properties": {
                    field: {"type": "string"} for field in (required or [])
                },
                "required": required or [],
                "additionalProperties": False,
            }
        ],
        "transcript": [call for _ in range(repeats)],
        "last_error": error,
        "remaining_budget": {"steps_left": 3, "tool_calls_left": 3, "retries_left": 1},
    }


def candidate(
    *,
    experience_id: str,
    text: str,
    rank: int,
    score: float,
    source: dict,
):
    return extract_candidate_features(
        experience_id=experience_id,
        natural_text=text,
        original_rank=rank,
        tfidf_score=score,
        source_observation=source,
    )


class ProperV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        payload = yaml.safe_load(
            (ROOT / "configs" / "proper_v1" / "candidate_rules.yaml").read_text(encoding="utf-8")
        )
        cls.rules = RuleSet.from_mapping(payload)
        cls.retry_text = "I retried the original tool call once and succeeded."
        cls.repair_text = "I corrected the missing arguments and succeeded."
        cls.stop_text = "I stopped without another tool call and reported the failure."

    def test_hidden_evaluator_field_is_rejected_recursively(self) -> None:
        with self.assertRaisesRegex(ValueError, "forbidden selector input"):
            assert_observable_payload({"public": {"fault_plan": []}})

    def test_failure_state_uses_public_argument_presence(self) -> None:
        omission = extract_failure_features(
            observation(code="missing_required_arg", args={}, missing=["x"], required=["x"])
        )
        contradiction = extract_failure_features(
            observation(
                code="missing_required_arg",
                args={"x": "present"},
                missing=["x"],
                required=["x"],
            )
        )
        self.assertEqual(omission.state, FailureState.ARGUMENT_OMISSION)
        self.assertEqual(contradiction.state, FailureState.MISSING_CLAIM_PRESENT)

    def test_repeated_authorization_is_observable(self) -> None:
        first = extract_failure_features(observation(code="authz_denied", args={}, repeats=1))
        repeated = extract_failure_features(
            observation(code="authz_denied", args={}, repeats=2)
        )
        self.assertEqual(first.state, FailureState.AUTHORIZATION_FIRST_DENIAL)
        self.assertEqual(repeated.state, FailureState.AUTHORIZATION_REPEATED_DENIAL)

    def test_policy_parser_has_explicit_unknown(self) -> None:
        self.assertEqual(parse_policy_from_text(self.retry_text), PolicyClass.RETRY)
        self.assertEqual(parse_policy_from_text(self.repair_text), PolicyClass.REPAIR)
        self.assertEqual(parse_policy_from_text(self.stop_text), PolicyClass.STOP)
        self.assertEqual(parse_policy_from_text("No recovery action stated."), PolicyClass.UNKNOWN)

    def test_timeout_ranks_retry_above_higher_tfidf_stop(self) -> None:
        target = extract_failure_features(observation(code="timeout", args={"x": "1"}))
        source = observation(code="timeout", args={"x": "1"})
        values = [
            candidate(
                experience_id="stop",
                text=self.stop_text,
                rank=1,
                score=0.9,
                source=source,
            ),
            candidate(
                experience_id="retry",
                text=self.retry_text,
                rank=2,
                score=0.8,
                source=source,
            ),
        ]
        ranked = rerank_candidates(target=target, candidates=values, rules=self.rules)
        self.assertEqual(ranked[0].candidate.experience_id, "retry")

    def test_argument_omission_requires_matching_repair_target(self) -> None:
        target = extract_failure_features(
            observation(code="missing_required_arg", args={}, missing=["x"], required=["x"])
        )
        wrong = observation(code="missing_required_arg", args={}, missing=["y"], required=["y"])
        right = observation(code="missing_required_arg", args={}, missing=["x"], required=["x"])
        values = [
            candidate(
                experience_id="wrong",
                text=self.repair_text,
                rank=1,
                score=0.9,
                source=wrong,
            ),
            candidate(
                experience_id="right",
                text=self.repair_text,
                rank=2,
                score=0.8,
                source=right,
            ),
        ]
        ranked = rerank_candidates(target=target, candidates=values, rules=self.rules)
        self.assertEqual(ranked[0].candidate.experience_id, "right")

    def test_missing_claim_present_ranks_retry_above_repair(self) -> None:
        target = extract_failure_features(
            observation(
                code="missing_required_arg",
                args={"x": "present"},
                missing=["x"],
                required=["x"],
            )
        )
        source = observation(code="missing_required_arg", args={}, missing=["x"], required=["x"])
        values = [
            candidate(
                experience_id="repair",
                text=self.repair_text,
                rank=1,
                score=0.9,
                source=source,
            ),
            candidate(
                experience_id="retry",
                text=self.retry_text,
                rank=2,
                score=0.8,
                source=source,
            ),
        ]
        ranked = rerank_candidates(target=target, candidates=values, rules=self.rules)
        self.assertEqual(ranked[0].candidate.experience_id, "retry")

    def test_first_authorization_preserves_tfidf_between_retry_and_stop(self) -> None:
        target = extract_failure_features(observation(code="authz_denied", args={"x": "1"}))
        source = observation(code="authz_denied", args={"x": "1"})
        values = [
            candidate(
                experience_id="stop",
                text=self.stop_text,
                rank=1,
                score=0.9,
                source=source,
            ),
            candidate(
                experience_id="retry",
                text=self.retry_text,
                rank=2,
                score=0.8,
                source=source,
            ),
        ]
        ranked = rerank_candidates(target=target, candidates=values, rules=self.rules)
        self.assertEqual(ranked[0].candidate.experience_id, "stop")

    def test_repeated_authorization_ranks_stop_above_retry(self) -> None:
        target = extract_failure_features(
            observation(code="authz_denied", args={"x": "1"}, repeats=2)
        )
        source = observation(code="authz_denied", args={"x": "1"})
        values = [
            candidate(
                experience_id="retry",
                text=self.retry_text,
                rank=1,
                score=0.9,
                source=source,
            ),
            candidate(
                experience_id="stop",
                text=self.stop_text,
                rank=2,
                score=0.8,
                source=source,
            ),
        ]
        ranked = rerank_candidates(target=target, candidates=values, rules=self.rules)
        self.assertEqual(ranked[0].candidate.experience_id, "stop")

    def test_ranking_is_independent_of_candidate_input_order(self) -> None:
        target = extract_failure_features(observation(code="timeout", args={"x": "1"}))
        source = observation(code="timeout", args={"x": "1"})
        values = [
            candidate(
                experience_id="b",
                text=self.retry_text,
                rank=2,
                score=0.8,
                source=source,
            ),
            candidate(
                experience_id="a",
                text=self.retry_text,
                rank=1,
                score=0.8,
                source=source,
            ),
        ]
        forward = rerank_candidates(target=target, candidates=values, rules=self.rules)
        reverse = rerank_candidates(target=target, candidates=list(reversed(values)), rules=self.rules)
        self.assertEqual(
            [item.candidate.experience_id for item in forward],
            [item.candidate.experience_id for item in reverse],
        )


if __name__ == "__main__":
    unittest.main()
