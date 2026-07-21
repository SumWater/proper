"""Source-blind retrieval and inapplicability-funnel measurement."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from .contracts import RecoveryPolicy


TOKEN_PATTERN = re.compile(r"[a-z0-9_]+", re.IGNORECASE)


def tokenize(text: str) -> tuple[str, ...]:
    return tuple(token.lower() for token in TOKEN_PATTERN.findall(text))


@dataclass(frozen=True)
class Experience:
    experience_id: str
    source_instance_id: str
    natural_text: str
    policy: RecoveryPolicy
    provenance: str


@dataclass(frozen=True)
class FailureQuery:
    instance_id: str
    natural_text: str
    provenance: str


@dataclass(frozen=True)
class RankedExperience:
    experience: Experience
    score: float
    rank: int


@dataclass(frozen=True)
class RetrievalFunnelRecord:
    instance_id: str
    candidate_inapplicability: bool
    selected_inapplicability: bool
    exposed_inapplicability: bool
    selected_experience_id: str | None
    selected_score: float | None


class SourceBlindTfidfRetriever:
    """Small deterministic lexical baseline that never reads provenance."""

    def __init__(self, experiences: Sequence[Experience]) -> None:
        if not experiences:
            raise ValueError("at least one experience is required")
        ids = [experience.experience_id for experience in experiences]
        if len(ids) != len(set(ids)):
            raise ValueError("experience_id values must be unique")
        self._experiences = tuple(experiences)
        self._document_counts = tuple(Counter(tokenize(item.natural_text)) for item in experiences)
        document_frequency: Counter[str] = Counter()
        for counts in self._document_counts:
            document_frequency.update(counts.keys())
        size = len(experiences)
        self._idf = {
            token: math.log((1.0 + size) / (1.0 + frequency)) + 1.0
            for token, frequency in document_frequency.items()
        }
        self._vectors = tuple(self._vector(counts) for counts in self._document_counts)

    def retrieve(
        self,
        query: FailureQuery,
        *,
        top_k: int,
        exclude_source_instance: bool = True,
    ) -> list[RankedExperience]:
        if top_k < 1:
            raise ValueError("top_k must be >= 1")
        query_vector = self._vector(Counter(tokenize(query.natural_text)))
        scored: list[tuple[float, Experience]] = []
        for experience, vector in zip(self._experiences, self._vectors, strict=True):
            if exclude_source_instance and experience.source_instance_id == query.instance_id:
                continue
            scored.append((self._cosine(query_vector, vector), experience))
        scored.sort(key=lambda item: (-item[0], item[1].experience_id))
        return [
            RankedExperience(experience=experience, score=score, rank=index)
            for index, (score, experience) in enumerate(scored[:top_k], start=1)
        ]

    def _vector(self, counts: Mapping[str, int]) -> dict[str, float]:
        total = sum(counts.values())
        if total == 0:
            return {}
        return {
            token: (count / total) * self._idf.get(token, 1.0)
            for token, count in counts.items()
        }

    @staticmethod
    def _cosine(left: Mapping[str, float], right: Mapping[str, float]) -> float:
        if not left or not right:
            return 0.0
        common = left.keys() & right.keys()
        dot = sum(left[token] * right[token] for token in common)
        left_norm = math.sqrt(sum(value * value for value in left.values()))
        right_norm = math.sqrt(sum(value * value for value in right.values()))
        return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


def measure_retrieval_funnel(
    *,
    query: FailureQuery,
    candidates: Sequence[RankedExperience],
    applicability: Mapping[str, bool],
    exposed_experience_ids: Iterable[str] | None = None,
) -> RetrievalFunnelRecord:
    """Measure candidate, rank-1 selected, and actually exposed inapplicability.

    Applicability is keyed by full experience ID because policy parameters and
    target instance jointly determine applicability; policy kind alone is not
    sufficient.
    """

    missing = [
        item.experience.experience_id
        for item in candidates
        if item.experience.experience_id not in applicability
    ]
    if missing:
        raise ValueError(f"missing applicability labels: {missing}")
    selected = candidates[0] if candidates else None
    candidate_inapplicability = any(
        not applicability[item.experience.experience_id] for item in candidates
    )
    selected_inapplicability = bool(
        selected is not None and not applicability[selected.experience.experience_id]
    )
    exposed_ids = set(exposed_experience_ids or ())
    exposed_inapplicability = any(
        experience_id in applicability and not applicability[experience_id]
        for experience_id in exposed_ids
    )
    return RetrievalFunnelRecord(
        instance_id=query.instance_id,
        candidate_inapplicability=candidate_inapplicability,
        selected_inapplicability=selected_inapplicability,
        exposed_inapplicability=exposed_inapplicability,
        selected_experience_id=(selected.experience.experience_id if selected else None),
        selected_score=(selected.score if selected else None),
    )


def aggregate_funnel(records: Sequence[RetrievalFunnelRecord]) -> dict[str, float | int]:
    if not records:
        raise ValueError("at least one funnel record is required")
    count = len(records)
    candidate = sum(record.candidate_inapplicability for record in records)
    selected = sum(record.selected_inapplicability for record in records)
    exposed = sum(record.exposed_inapplicability for record in records)
    return {
        "query_count": count,
        "candidate_inapplicability_count": candidate,
        "candidate_inapplicability_rate": candidate / count,
        "selected_inapplicability_count": selected,
        "selected_inapplicability_rate": selected / count,
        "exposed_inapplicability_count": exposed,
        "exposed_inapplicability_rate": exposed / count,
    }
