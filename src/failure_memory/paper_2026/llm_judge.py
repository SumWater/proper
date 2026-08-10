"""Frozen prompt and strict parser for the paper's LLM reranker baseline."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


PROMPT_VERSION = "llm_applicability_judge_v0_1_frozen"
SYSTEM_MESSAGE = (
    "You are a conservative applicability reranker for a tool-using agent after a failed "
    "tool call. Use only the observable failure context and candidate memory text supplied "
    "by the user. Do not infer hidden benchmark labels, gold actions, recoverability, or "
    "evaluation outcomes. Select the one memory whose trigger, preconditions, and recovery "
    "guidance are most applicable and safe for the observed failure. Avoid guidance that is "
    "contradicted by the context. If candidates are equally applicable, select the smaller "
    "candidate_position. Return exactly one JSON object with no markdown or explanation. "
    "The object must have exactly one key named selected_candidate_id, and its string value "
    "must be one supplied candidate_id."
)

REQUIRED_CONTEXT_KEYS = frozenset(
    {
        "user_instruction",
        "failed_tool_name",
        "failed_arguments",
        "public_error_or_return",
        "remaining_retry_budget",
        "public_tool_schemas",
        "observable_history",
    }
)
_CANDIDATE_ID = re.compile(r"C[0-9]{2,}")


@dataclass(frozen=True)
class JudgeCandidate:
    candidate_id: str
    memory_text: str

    def __post_init__(self) -> None:
        if not _CANDIDATE_ID.fullmatch(self.candidate_id):
            raise ValueError("candidate_id must match C followed by at least two digits")
        if not self.memory_text.strip():
            raise ValueError("candidate memory text must be nonempty")


@dataclass(frozen=True)
class JudgeDecision:
    selected_candidate_id: str
    parse_succeeded: bool
    fallback_used: bool
    reason_code: str

    def to_mapping(self) -> dict[str, Any]:
        return {
            "selected_candidate_id": self.selected_candidate_id,
            "parse_succeeded": self.parse_succeeded,
            "fallback_used": self.fallback_used,
            "reason_code": self.reason_code,
        }


def _validate_inputs(
    failure_context: Mapping[str, Any], candidates: Sequence[JudgeCandidate]
) -> None:
    keys = frozenset(failure_context)
    if keys != REQUIRED_CONTEXT_KEYS:
        missing = sorted(REQUIRED_CONTEXT_KEYS - keys)
        extra = sorted(keys - REQUIRED_CONTEXT_KEYS)
        raise ValueError(f"failure context key mismatch: missing={missing}, extra={extra}")
    if not candidates:
        raise ValueError("at least one candidate is required")
    ids = [candidate.candidate_id for candidate in candidates]
    if len(ids) != len(set(ids)):
        raise ValueError("candidate IDs must be unique")


def build_judge_messages(
    failure_context: Mapping[str, Any], candidates: Sequence[JudgeCandidate]
) -> list[dict[str, str]]:
    """Build the exact source-blind reranking prompt.

    Candidate order is the frozen TF-IDF order, and ``candidate_position`` is the
    deterministic tie-breaker. Experience IDs and provenance are intentionally absent.
    """
    _validate_inputs(failure_context, candidates)
    payload = {
        "task": "select_one_applicable_recovery_memory",
        "failure_context": dict(failure_context),
        "candidates": [
            {
                "candidate_id": candidate.candidate_id,
                "candidate_position": position,
                "memory_text": candidate.memory_text,
            }
            for position, candidate in enumerate(candidates, start=1)
        ],
        "required_output_schema": {"selected_candidate_id": "supplied candidate_id"},
    }
    return [
        {"role": "system", "content": SYSTEM_MESSAGE},
        {
            "role": "user",
            "content": json.dumps(
                payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
            ),
        },
    ]


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_judge_response(raw_text: str, candidate_ids: Sequence[str]) -> str:
    parsed = json.loads(raw_text.strip(), object_pairs_hook=_object_without_duplicate_keys)
    if not isinstance(parsed, dict) or set(parsed) != {"selected_candidate_id"}:
        raise ValueError("judge response must contain exactly selected_candidate_id")
    selected = parsed["selected_candidate_id"]
    if not isinstance(selected, str) or selected not in set(candidate_ids):
        raise ValueError("judge selected an unknown candidate ID")
    return selected


def decide_with_rank1_fallback(
    raw_text: str, candidates: Sequence[JudgeCandidate]
) -> JudgeDecision:
    if not candidates:
        raise ValueError("at least one candidate is required")
    candidate_ids = [candidate.candidate_id for candidate in candidates]
    try:
        selected = parse_judge_response(raw_text, candidate_ids)
    except (json.JSONDecodeError, ValueError):
        return JudgeDecision(
            selected_candidate_id=candidate_ids[0],
            parse_succeeded=False,
            fallback_used=True,
            reason_code="invalid_output_fallback_to_tfidf_rank1",
        )
    return JudgeDecision(
        selected_candidate_id=selected,
        parse_succeeded=True,
        fallback_used=False,
        reason_code="strict_json_selection",
    )
