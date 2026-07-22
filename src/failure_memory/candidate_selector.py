"""Observable-evidence-only deterministic reranking for PROPER v1."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence


FORBIDDEN_INPUT_KEYS = frozenset(
    {
        "fault_plan",
        "fault_type",
        "recoverability",
        "gold_summary",
        "success_criteria",
        "provenance",
        "recommended_policy",
        "environment_applicability",
        "recovery_validity_outcome",
        "matched_applicable_experience_id",
    }
)


class PolicyClass(str, Enum):
    RETRY = "retry"
    REPAIR = "repair"
    STOP = "stop"
    UNKNOWN = "unknown"


class FailureState(str, Enum):
    TIMEOUT = "timeout"
    ARGUMENT_OMISSION = "argument_omission"
    MISSING_CLAIM_PRESENT = "missing_claim_present"
    AUTHORIZATION_FIRST_DENIAL = "authorization_first_denial"
    AUTHORIZATION_REPEATED_DENIAL = "authorization_repeated_denial"
    UNKNOWN = "unknown"


class Compatibility(str, Enum):
    INCOMPATIBLE = "incompatible"
    UNCERTAIN = "uncertain"
    COMPATIBLE = "compatible"

    @property
    def rank(self) -> int:
        return {
            Compatibility.INCOMPATIBLE: 0,
            Compatibility.UNCERTAIN: 1,
            Compatibility.COMPATIBLE: 2,
        }[self]


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def assert_observable_payload(value: Any, path: str = "$") -> None:
    """Reject evaluator-only field names recursively before feature extraction."""

    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).lower()
            if normalized in FORBIDDEN_INPUT_KEYS:
                raise ValueError(f"forbidden selector input at {path}.{key}")
            assert_observable_payload(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            assert_observable_payload(child, f"{path}[{index}]")


def flatten_argument_paths(value: Any, prefix: str = "") -> tuple[str, ...]:
    if not isinstance(value, Mapping):
        return (prefix or "/",)
    paths: list[str] = []
    for key in sorted(value, key=str):
        escaped = str(key).replace("~", "~0").replace("/", "~1")
        child_path = f"{prefix}/{escaped}"
        child = value[key]
        if isinstance(child, Mapping) and child:
            paths.extend(flatten_argument_paths(child, child_path))
        else:
            paths.append(child_path)
    return tuple(paths)


def _failed_call(observation: Mapping[str, Any]) -> Mapping[str, Any]:
    transcript = observation.get("transcript", [])
    if not isinstance(transcript, list) or not transcript:
        raise ValueError("observable transcript must contain the failed call")
    failed = transcript[-1]
    if not isinstance(failed, Mapping) or "tool_name" not in failed:
        raise ValueError("last transcript entry is not a public tool call")
    return failed


def _tool_schema(
    observation: Mapping[str, Any], tool_name: str
) -> Mapping[str, Any] | None:
    schemas = observation.get("tool_schemas", [])
    if not isinstance(schemas, list):
        return None
    return next(
        (
            schema
            for schema in schemas
            if isinstance(schema, Mapping) and schema.get("name") == tool_name
        ),
        None,
    )


def schema_signature(schema: Mapping[str, Any] | None) -> str | None:
    if schema is None:
        return None
    payload = {
        "properties": schema.get("properties", {}),
        "required": sorted(str(value) for value in schema.get("required", [])),
        "additionalProperties": schema.get("additionalProperties"),
    }
    return canonical(payload)


def _has_top_level_argument(arguments: Mapping[str, Any], field: str) -> bool:
    return field in arguments


def classify_failure_state(
    *,
    error_code: str | None,
    missing_fields: Sequence[str],
    failed_arguments: Mapping[str, Any],
    repeated_same_call_count: int,
) -> FailureState:
    if error_code == "timeout":
        return FailureState.TIMEOUT
    if error_code == "missing_required_arg" and missing_fields:
        if all(_has_top_level_argument(failed_arguments, field) for field in missing_fields):
            return FailureState.MISSING_CLAIM_PRESENT
        return FailureState.ARGUMENT_OMISSION
    if error_code == "authz_denied":
        if repeated_same_call_count >= 2:
            return FailureState.AUTHORIZATION_REPEATED_DENIAL
        return FailureState.AUTHORIZATION_FIRST_DENIAL
    return FailureState.UNKNOWN


@dataclass(frozen=True)
class FailureFeatures:
    tool_name: str
    error_code: str | None
    state: FailureState
    failed_arguments: Mapping[str, Any]
    failed_argument_paths: tuple[str, ...]
    missing_fields: tuple[str, ...]
    public_schema_fields: tuple[str, ...]
    public_required_fields: tuple[str, ...]
    schema_signature: str | None
    repeated_same_call_count: int


def extract_failure_features(observation: Mapping[str, Any]) -> FailureFeatures:
    assert_observable_payload(observation)
    failed = _failed_call(observation)
    tool_name = str(failed["tool_name"])
    arguments = failed.get("args", {})
    if not isinstance(arguments, Mapping):
        raise ValueError("failed tool arguments must be an object")
    error = observation.get("last_error") or failed.get("error") or {}
    if not isinstance(error, Mapping):
        raise ValueError("last_error must be an object")
    details = error.get("details") or {}
    if not isinstance(details, Mapping):
        details = {}
    missing = tuple(sorted(str(value) for value in details.get("missing", [])))
    transcript = observation.get("transcript", [])
    repeated = sum(
        isinstance(item, Mapping)
        and item.get("tool_name") == tool_name
        and canonical(item.get("args", {})) == canonical(arguments)
        for item in transcript
    )
    schema = _tool_schema(observation, tool_name)
    properties = schema.get("properties", {}) if schema else {}
    required = schema.get("required", []) if schema else []
    error_code = str(error["code"]) if error.get("code") is not None else None
    return FailureFeatures(
        tool_name=tool_name,
        error_code=error_code,
        state=classify_failure_state(
            error_code=error_code,
            missing_fields=missing,
            failed_arguments=arguments,
            repeated_same_call_count=repeated,
        ),
        failed_arguments=dict(arguments),
        failed_argument_paths=flatten_argument_paths(arguments),
        missing_fields=missing,
        public_schema_fields=tuple(sorted(str(value) for value in properties)),
        public_required_fields=tuple(sorted(str(value) for value in required)),
        schema_signature=schema_signature(schema),
        repeated_same_call_count=repeated,
    )


def parse_policy_from_text(natural_text: str) -> PolicyClass:
    lowered = natural_text.lower()
    if "retried the original tool call once" in lowered:
        return PolicyClass.RETRY
    if "corrected the missing arguments" in lowered:
        return PolicyClass.REPAIR
    if "stopped without another tool call" in lowered:
        return PolicyClass.STOP
    return PolicyClass.UNKNOWN


@dataclass(frozen=True)
class CandidateFeatures:
    experience_id: str
    natural_text: str
    original_rank: int
    tfidf_score: float
    source_failure: FailureFeatures
    policy: PolicyClass
    repair_targets: tuple[str, ...]


def extract_candidate_features(
    *,
    experience_id: str,
    natural_text: str,
    original_rank: int,
    tfidf_score: float,
    source_observation: Mapping[str, Any],
) -> CandidateFeatures:
    assert_observable_payload(source_observation)
    source = extract_failure_features(source_observation)
    policy = parse_policy_from_text(natural_text)
    repair_targets = source.missing_fields if policy == PolicyClass.REPAIR else ()
    return CandidateFeatures(
        experience_id=experience_id,
        natural_text=natural_text,
        original_rank=original_rank,
        tfidf_score=tfidf_score,
        source_failure=source,
        policy=policy,
        repair_targets=repair_targets,
    )


@dataclass(frozen=True)
class RuleSet:
    compatibility_matrix: Mapping[str, Mapping[str, str]]
    enabled_contradictions: frozenset[str]

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "RuleSet":
        matrix = payload.get("compatibility_matrix")
        contradictions = payload.get("enabled_contradictions")
        if not isinstance(matrix, Mapping) or not isinstance(contradictions, list):
            raise ValueError("rules require compatibility_matrix and enabled_contradictions")
        return cls(
            compatibility_matrix=matrix,
            enabled_contradictions=frozenset(str(value) for value in contradictions),
        )


def policy_compatibility(
    target: FailureFeatures, candidate: CandidateFeatures, rules: RuleSet
) -> Compatibility:
    row = rules.compatibility_matrix.get(target.state.value, {})
    value = row.get(candidate.policy.value, Compatibility.UNCERTAIN.value)
    return Compatibility(value)


def repair_target_agreement(
    target: FailureFeatures, candidate: CandidateFeatures
) -> int:
    if candidate.policy != PolicyClass.REPAIR:
        return 0
    expected = set(target.missing_fields)
    proposed = set(candidate.repair_targets)
    if not expected or not proposed:
        return 0
    if expected == proposed:
        return 2
    return int(bool(expected & proposed))


def failure_evidence_agreement(
    target: FailureFeatures, candidate: CandidateFeatures
) -> int:
    if target.error_code == candidate.source_failure.error_code:
        return 2
    if target.state == candidate.source_failure.state:
        return 1
    return 0


def tool_compatibility(target: FailureFeatures, candidate: CandidateFeatures) -> int:
    source = candidate.source_failure
    if target.tool_name == source.tool_name:
        return 2
    if (
        target.schema_signature is not None
        and target.schema_signature == source.schema_signature
    ):
        return 1
    return 0


def contradictions(
    target: FailureFeatures, candidate: CandidateFeatures, rules: RuleSet
) -> tuple[str, ...]:
    found: list[str] = []

    def add(name: str, condition: bool) -> None:
        if condition and name in rules.enabled_contradictions:
            found.append(name)

    add(
        "retry_with_public_argument_omission",
        target.state == FailureState.ARGUMENT_OMISSION
        and candidate.policy == PolicyClass.RETRY,
    )
    add(
        "repair_target_mismatch",
        candidate.policy == PolicyClass.REPAIR
        and target.state == FailureState.ARGUMENT_OMISSION
        and repair_target_agreement(target, candidate) == 0,
    )
    add(
        "repair_when_claimed_missing_is_present",
        target.state == FailureState.MISSING_CLAIM_PRESENT
        and candidate.policy == PolicyClass.REPAIR,
    )
    add(
        "stop_on_directly_recoverable_failure",
        target.state
        in {FailureState.TIMEOUT, FailureState.ARGUMENT_OMISSION, FailureState.MISSING_CLAIM_PRESENT}
        and candidate.policy == PolicyClass.STOP,
    )
    add(
        "retry_after_repeated_authorization_denial",
        target.state == FailureState.AUTHORIZATION_REPEATED_DENIAL
        and candidate.policy == PolicyClass.RETRY,
    )
    add(
        "repair_nonexistent_public_field",
        candidate.policy == PolicyClass.REPAIR
        and bool(candidate.repair_targets)
        and not set(candidate.repair_targets).issubset(set(target.public_schema_fields)),
    )
    return tuple(sorted(found))


@dataclass(frozen=True)
class CandidateScore:
    experience_id: str
    original_rank: int
    tfidf_score: float
    contradictions: tuple[str, ...]
    policy_compatibility: Compatibility
    repair_target_agreement: int
    failure_evidence_agreement: int
    tool_compatibility: int
    authorization_tie_preserved: bool

    def sort_key(self) -> tuple[Any, ...]:
        if self.authorization_tie_preserved:
            return (
                len(self.contradictions),
                -self.policy_compatibility.rank,
                0,
                0,
                0,
                -self.tfidf_score,
                self.experience_id,
            )
        return (
            len(self.contradictions),
            -self.policy_compatibility.rank,
            -self.repair_target_agreement,
            -self.failure_evidence_agreement,
            -self.tool_compatibility,
            -self.tfidf_score,
            self.experience_id,
        )


def score_candidate(
    target: FailureFeatures, candidate: CandidateFeatures, rules: RuleSet
) -> CandidateScore:
    compatibility = policy_compatibility(target, candidate, rules)
    preserve_auth_tie = (
        target.state == FailureState.AUTHORIZATION_FIRST_DENIAL
        and candidate.policy in {PolicyClass.RETRY, PolicyClass.STOP}
        and compatibility == Compatibility.UNCERTAIN
    )
    return CandidateScore(
        experience_id=candidate.experience_id,
        original_rank=candidate.original_rank,
        tfidf_score=candidate.tfidf_score,
        contradictions=contradictions(target, candidate, rules),
        policy_compatibility=compatibility,
        repair_target_agreement=repair_target_agreement(target, candidate),
        failure_evidence_agreement=failure_evidence_agreement(target, candidate),
        tool_compatibility=tool_compatibility(target, candidate),
        authorization_tie_preserved=preserve_auth_tie,
    )


@dataclass(frozen=True)
class RerankedCandidate:
    candidate: CandidateFeatures
    score: CandidateScore
    proper_rank: int


def rerank_candidates(
    *,
    target: FailureFeatures,
    candidates: Sequence[CandidateFeatures],
    rules: RuleSet,
) -> list[RerankedCandidate]:
    if not candidates:
        raise ValueError("at least one candidate is required")
    ids = [item.experience_id for item in candidates]
    if len(ids) != len(set(ids)):
        raise ValueError("candidate experience IDs must be unique")
    scored = [(candidate, score_candidate(target, candidate, rules)) for candidate in candidates]
    scored.sort(key=lambda item: item[1].sort_key())
    return [
        RerankedCandidate(candidate=candidate, score=score, proper_rank=index)
        for index, (candidate, score) in enumerate(scored, start=1)
    ]


def score_payload(value: CandidateScore) -> dict[str, Any]:
    payload = asdict(value)
    payload["policy_compatibility"] = value.policy_compatibility.value
    return payload
