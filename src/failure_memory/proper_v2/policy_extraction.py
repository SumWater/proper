"""Deterministic ingestion of frozen structured memory-policy cards."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .boundary import memory_policy_card_from_mapping
from .contracts import MemoryPolicyCard


def load_policy_cards(
    payloads: Sequence[Mapping[str, Any]],
) -> tuple[MemoryPolicyCard, ...]:
    """Load structured cards without inferring hidden applicability or outcomes."""

    cards = tuple(memory_policy_card_from_mapping(payload) for payload in payloads)
    ids = [card.experience_id for card in cards]
    ranks = [card.original_rank for card in cards]
    if not cards:
        raise ValueError("at least one memory policy card is required")
    if len(ids) != len(set(ids)):
        raise ValueError("memory policy card experience IDs must be unique")
    if len(ranks) != len(set(ranks)) or min(ranks) != 1:
        raise ValueError("original ranks must be unique and include Rank-1")
    return cards
