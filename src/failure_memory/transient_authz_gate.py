"""Conservative memory selection for the released transient-authz stratum."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .candidate_selector import (
    FailureFeatures,
    FailureState,
    PolicyClass,
    assert_observable_payload,
    extract_failure_features,
)


@dataclass(frozen=True)
class TransientAuthzCandidate:
    experience_id: str
    original_rank: int
    policy: PolicyClass
    source_tool_name: str

    @classmethod
    def from_public_mapping(cls, payload: Mapping[str, Any]) -> "TransientAuthzCandidate":
        assert_observable_payload(payload)
        source = payload.get("source_failure")
        if not isinstance(source, Mapping):
            raise ValueError("candidate source_failure must be an object")
        rank = int(payload["original_rank"])
        if rank < 1:
            raise ValueError("candidate original_rank must be positive")
        return cls(
            experience_id=str(payload["experience_id"]),
            original_rank=rank,
            policy=PolicyClass(str(payload["policy_from_text"])),
            source_tool_name=str(source["tool_name"]),
        )


@dataclass(frozen=True)
class TransientAuthzDecision:
    selected_experience_id: str
    selected_original_rank: int
    selection_changed: bool
    rank1_policy: PolicyClass
    same_tool_memory: bool
    reason_code: str


def select_for_features(
    features: FailureFeatures,
    candidates: Sequence[TransientAuthzCandidate],
) -> TransientAuthzDecision:
    if features.state != FailureState.AUTHORIZATION_FIRST_DENIAL:
        raise ValueError("transient-authz gate requires a first authz_denied observation")
    if not candidates:
        raise ValueError("at least one candidate is required")
    ranks = [item.original_rank for item in candidates]
    if len(ranks) != len(set(ranks)) or min(ranks) != 1:
        raise ValueError("candidate ranks must be unique and include Rank-1")
    rank1 = next(item for item in candidates if item.original_rank == 1)
    if rank1.policy == PolicyClass.RETRY:
        selected = rank1
        reason = "preserve_rank1_retry_memory"
    else:
        retry_candidates = [item for item in candidates if item.policy == PolicyClass.RETRY]
        if not retry_candidates:
            raise ValueError("Top-k has no retry memory for released transient authorization")
        retry_candidates.sort(
            key=lambda item: (
                item.source_tool_name != features.tool_name,
                item.original_rank,
            )
        )
        selected = retry_candidates[0]
        reason = "replace_nonretry_rank1_with_retry_memory"
    return TransientAuthzDecision(
        selected_experience_id=selected.experience_id,
        selected_original_rank=selected.original_rank,
        selection_changed=selected.experience_id != rank1.experience_id,
        rank1_policy=rank1.policy,
        same_tool_memory=selected.source_tool_name == features.tool_name,
        reason_code=reason,
    )


def select_transient_authz_memory(
    observation: Mapping[str, Any],
    candidates: Sequence[TransientAuthzCandidate],
) -> TransientAuthzDecision:
    assert_observable_payload(observation)
    return select_for_features(extract_failure_features(observation), candidates)
