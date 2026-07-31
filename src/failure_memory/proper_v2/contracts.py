"""Typed contracts for unified PROPER v2 development."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence


def _unique_strings(values: Sequence[Any], field_name: str) -> tuple[str, ...]:
    normalized = tuple(sorted(str(value) for value in values))
    if any(not value for value in normalized):
        raise ValueError(f"{field_name} cannot contain empty strings")
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{field_name} must contain unique values")
    return normalized


class RetrySafety(str, Enum):
    SAFE = "safe"
    UNSAFE = "unsafe"
    UNKNOWN = "unknown"


class DecisionPhase(str, Enum):
    PRE_ACTION = "pre_action"
    POST_FAILURE = "post_failure"


class RecoveryOperation(str, Enum):
    REPAIR_ARGUMENTS = "repair_arguments"
    RETRY_SAME_ACTION = "retry_same_action"
    INVOKE_PREREQUISITE = "invoke_prerequisite"
    SWITCH_TOOL = "switch_tool"
    USE_FALLBACK = "use_fallback"
    REQUEST_INFORMATION = "request_information"
    STOP_AND_REPORT = "stop_and_report"
    UNKNOWN = "unknown"


class ContinuationPolicy(str, Enum):
    CONTINUE_DIRECTLY = "continue_directly"
    VERIFY_THEN_CONTINUE = "verify_then_continue"
    RETRY_THEN_VERIFY = "retry_then_verify"
    TERMINATE = "terminate"
    UNKNOWN = "unknown"


class TruthStatus(str, Enum):
    SATISFIED = "satisfied"
    VIOLATED = "violated"
    UNKNOWN = "unknown"

    @property
    def rank(self) -> int:
        return {
            TruthStatus.VIOLATED: 0,
            TruthStatus.UNKNOWN: 1,
            TruthStatus.SATISFIED: 2,
        }[self]


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


@dataclass(frozen=True)
class RetrySafetyAssessment:
    status: RetrySafety
    evidence_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "evidence_codes",
            _unique_strings(self.evidence_codes, "retry_safety.evidence_codes"),
        )
        if self.status != RetrySafety.UNKNOWN and not self.evidence_codes:
            raise ValueError("known retry safety requires public evidence")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "RetrySafetyAssessment":
        return cls(
            status=RetrySafety(str(payload["status"])),
            evidence_codes=tuple(payload.get("evidence_codes", ())),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "evidence_codes": list(self.evidence_codes),
        }


@dataclass(frozen=True)
class ProposedAction:
    tool_name: str
    argument_template: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not self.tool_name:
            raise ValueError("proposed action tool_name cannot be empty")
        object.__setattr__(self, "argument_template", dict(self.argument_template))

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ProposedAction":
        arguments = payload.get("argument_template")
        if not isinstance(arguments, Mapping):
            raise ValueError("proposed action argument_template must be an object")
        return cls(tool_name=str(payload["tool_name"]), argument_template=arguments)

    def to_mapping(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "argument_template": dict(self.argument_template),
        }


@dataclass(frozen=True)
class ObservableFailure:
    instruction: str
    tool_name: str
    failed_arguments: Mapping[str, Any]
    error_code: str | None
    evidence_codes: tuple[str, ...]
    failed_argument_paths: tuple[str, ...]
    missing_fields: tuple[str, ...]
    public_schema_fields: tuple[str, ...]
    public_required_fields: tuple[str, ...]
    available_tools: tuple[str, ...]
    available_capabilities: tuple[str, ...]
    satisfied_facts: tuple[str, ...]
    violated_facts: tuple[str, ...]
    repeated_same_call_count: int
    retry_safety: RetrySafetyAssessment

    def __post_init__(self) -> None:
        if not self.tool_name:
            raise ValueError("observable failure tool_name cannot be empty")
        if self.repeated_same_call_count < 1:
            raise ValueError("repeated_same_call_count must be positive")
        object.__setattr__(self, "failed_arguments", dict(self.failed_arguments))
        for field_name in (
            "evidence_codes",
            "failed_argument_paths",
            "missing_fields",
            "public_schema_fields",
            "public_required_fields",
            "available_tools",
            "available_capabilities",
            "satisfied_facts",
            "violated_facts",
        ):
            object.__setattr__(
                self,
                field_name,
                _unique_strings(getattr(self, field_name), field_name),
            )
        overlap = set(self.satisfied_facts) & set(self.violated_facts)
        if overlap:
            raise ValueError(f"public facts cannot be both satisfied and violated: {sorted(overlap)}")
        if self.tool_name not in self.available_tools:
            raise ValueError("failed tool must be present in available_tools")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ObservableFailure":
        if int(payload.get("schema_version", 0)) != 1:
            raise ValueError("unsupported observable failure schema_version")
        failed_action = payload.get("failed_action")
        if not isinstance(failed_action, Mapping):
            raise ValueError("failed_action must be an object")
        arguments = failed_action.get("arguments")
        if not isinstance(arguments, Mapping):
            raise ValueError("failed action arguments must be an object")
        retry_safety = payload.get("retry_safety")
        if not isinstance(retry_safety, Mapping):
            raise ValueError("retry_safety must be an object")
        return cls(
            instruction=str(payload["instruction"]),
            tool_name=str(failed_action["tool_name"]),
            failed_arguments=arguments,
            error_code=(
                str(payload["error_code"]) if payload.get("error_code") is not None else None
            ),
            evidence_codes=tuple(payload.get("evidence_codes", ())),
            failed_argument_paths=tuple(payload.get("failed_argument_paths", ())),
            missing_fields=tuple(payload.get("missing_fields", ())),
            public_schema_fields=tuple(payload.get("public_schema_fields", ())),
            public_required_fields=tuple(payload.get("public_required_fields", ())),
            available_tools=tuple(payload.get("available_tools", ())),
            available_capabilities=tuple(payload.get("available_capabilities", ())),
            satisfied_facts=tuple(payload.get("satisfied_facts", ())),
            violated_facts=tuple(payload.get("violated_facts", ())),
            repeated_same_call_count=int(payload["repeated_same_call_count"]),
            retry_safety=RetrySafetyAssessment.from_mapping(retry_safety),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "instruction": self.instruction,
            "failed_action": {
                "tool_name": self.tool_name,
                "arguments": dict(self.failed_arguments),
            },
            "error_code": self.error_code,
            "evidence_codes": list(self.evidence_codes),
            "failed_argument_paths": list(self.failed_argument_paths),
            "missing_fields": list(self.missing_fields),
            "public_schema_fields": list(self.public_schema_fields),
            "public_required_fields": list(self.public_required_fields),
            "available_tools": list(self.available_tools),
            "available_capabilities": list(self.available_capabilities),
            "satisfied_facts": list(self.satisfied_facts),
            "violated_facts": list(self.violated_facts),
            "repeated_same_call_count": self.repeated_same_call_count,
            "retry_safety": self.retry_safety.to_mapping(),
        }

    def to_recovery_state(self) -> "ObservableRecoveryState":
        """Losslessly adapt the frozen v2 post-failure contract to v2.1."""

        return ObservableRecoveryState(
            phase=DecisionPhase.POST_FAILURE,
            instruction=self.instruction,
            action=ProposedAction(
                tool_name=self.tool_name,
                argument_template=self.failed_arguments,
            ),
            error_code=self.error_code,
            evidence_codes=self.evidence_codes,
            failed_argument_paths=self.failed_argument_paths,
            missing_fields=self.missing_fields,
            public_schema_fields=self.public_schema_fields,
            public_required_fields=self.public_required_fields,
            available_tools=self.available_tools,
            available_capabilities=self.available_capabilities,
            satisfied_facts=self.satisfied_facts,
            violated_facts=self.violated_facts,
            repeated_same_call_count=self.repeated_same_call_count,
            retry_safety=self.retry_safety,
        )


@dataclass(frozen=True)
class ObservableRecoveryState:
    """Unified v2.1 state for decisions before an action or after a failure."""

    phase: DecisionPhase
    instruction: str
    action: ProposedAction | None
    error_code: str | None
    evidence_codes: tuple[str, ...]
    failed_argument_paths: tuple[str, ...]
    missing_fields: tuple[str, ...]
    public_schema_fields: tuple[str, ...]
    public_required_fields: tuple[str, ...]
    available_tools: tuple[str, ...]
    available_capabilities: tuple[str, ...]
    satisfied_facts: tuple[str, ...]
    violated_facts: tuple[str, ...]
    repeated_same_call_count: int
    retry_safety: RetrySafetyAssessment

    def __post_init__(self) -> None:
        for field_name in (
            "evidence_codes",
            "failed_argument_paths",
            "missing_fields",
            "public_schema_fields",
            "public_required_fields",
            "available_tools",
            "available_capabilities",
            "satisfied_facts",
            "violated_facts",
        ):
            object.__setattr__(
                self,
                field_name,
                _unique_strings(getattr(self, field_name), field_name),
            )
        overlap = set(self.satisfied_facts) & set(self.violated_facts)
        if overlap:
            raise ValueError(
                "public facts cannot be both satisfied and violated: "
                f"{sorted(overlap)}"
            )
        if self.action is not None and self.action.tool_name not in self.available_tools:
            raise ValueError("observed action tool must be present in available_tools")
        if self.phase == DecisionPhase.POST_FAILURE:
            if self.action is None:
                raise ValueError("post_failure state requires a failed action")
            if self.repeated_same_call_count < 1:
                raise ValueError(
                    "post_failure repeated_same_call_count must be positive"
                )
        else:
            if self.repeated_same_call_count != 0:
                raise ValueError(
                    "pre_action repeated_same_call_count must be zero"
                )
            if self.error_code is not None:
                raise ValueError("pre_action state cannot contain an error_code")
            if self.failed_argument_paths:
                raise ValueError(
                    "pre_action state cannot contain failed_argument_paths"
                )
            if self.retry_safety.status != RetrySafety.UNKNOWN:
                raise ValueError("pre_action retry safety must be unknown")

    @property
    def tool_name(self) -> str:
        return self.action.tool_name if self.action is not None else ""

    @property
    def failed_arguments(self) -> Mapping[str, Any]:
        return (
            self.action.argument_template
            if self.action is not None
            else {}
        )

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ObservableRecoveryState":
        if int(payload.get("schema_version", 0)) != 2:
            raise ValueError("unsupported observable recovery-state schema_version")
        action = payload.get("action")
        if action is not None and not isinstance(action, Mapping):
            raise ValueError("action must be an object or null")
        retry_safety = payload.get("retry_safety")
        if not isinstance(retry_safety, Mapping):
            raise ValueError("retry_safety must be an object")
        return cls(
            phase=DecisionPhase(str(payload["phase"])),
            instruction=str(payload["instruction"]),
            action=ProposedAction.from_mapping(action) if action else None,
            error_code=(
                str(payload["error_code"])
                if payload.get("error_code") is not None
                else None
            ),
            evidence_codes=tuple(payload.get("evidence_codes", ())),
            failed_argument_paths=tuple(
                payload.get("failed_argument_paths", ())
            ),
            missing_fields=tuple(payload.get("missing_fields", ())),
            public_schema_fields=tuple(
                payload.get("public_schema_fields", ())
            ),
            public_required_fields=tuple(
                payload.get("public_required_fields", ())
            ),
            available_tools=tuple(payload.get("available_tools", ())),
            available_capabilities=tuple(
                payload.get("available_capabilities", ())
            ),
            satisfied_facts=tuple(payload.get("satisfied_facts", ())),
            violated_facts=tuple(payload.get("violated_facts", ())),
            repeated_same_call_count=int(payload["repeated_same_call_count"]),
            retry_safety=RetrySafetyAssessment.from_mapping(retry_safety),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "phase": self.phase.value,
            "instruction": self.instruction,
            "action": self.action.to_mapping() if self.action else None,
            "error_code": self.error_code,
            "evidence_codes": list(self.evidence_codes),
            "failed_argument_paths": list(self.failed_argument_paths),
            "missing_fields": list(self.missing_fields),
            "public_schema_fields": list(self.public_schema_fields),
            "public_required_fields": list(self.public_required_fields),
            "available_tools": list(self.available_tools),
            "available_capabilities": list(self.available_capabilities),
            "satisfied_facts": list(self.satisfied_facts),
            "violated_facts": list(self.violated_facts),
            "repeated_same_call_count": self.repeated_same_call_count,
            "retry_safety": self.retry_safety.to_mapping(),
        }


@dataclass(frozen=True)
class MemoryPolicyCard:
    experience_id: str
    natural_text: str
    original_rank: int
    retrieval_score: float
    trigger_evidence: tuple[str, ...]
    required_preconditions: tuple[str, ...]
    recovery_operation: RecoveryOperation
    target_object: str | None
    proposed_action: ProposedAction | None
    repair_targets: tuple[str, ...]
    continuation_policy: ContinuationPolicy
    success_evidence: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    source_tool: str | None
    extraction_confidence: float

    def __post_init__(self) -> None:
        if not self.experience_id or not self.natural_text:
            raise ValueError("memory identity and natural_text cannot be empty")
        if self.original_rank < 1:
            raise ValueError("original_rank must be positive")
        if not 0.0 <= self.extraction_confidence <= 1.0:
            raise ValueError("extraction_confidence must be in [0, 1]")
        for field_name in (
            "trigger_evidence",
            "required_preconditions",
            "repair_targets",
            "success_evidence",
            "stop_conditions",
        ):
            object.__setattr__(
                self,
                field_name,
                _unique_strings(getattr(self, field_name), field_name),
            )
        if (
            self.recovery_operation
            in {
                RecoveryOperation.INVOKE_PREREQUISITE,
                RecoveryOperation.SWITCH_TOOL,
                RecoveryOperation.USE_FALLBACK,
            }
            and self.proposed_action is None
        ):
            raise ValueError(f"{self.recovery_operation.value} requires a proposed action")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "MemoryPolicyCard":
        if int(payload.get("schema_version", 0)) != 1:
            raise ValueError("unsupported memory policy card schema_version")
        proposed = payload.get("proposed_action")
        if proposed is not None and not isinstance(proposed, Mapping):
            raise ValueError("proposed_action must be an object or null")
        return cls(
            experience_id=str(payload["experience_id"]),
            natural_text=str(payload["natural_text"]),
            original_rank=int(payload["original_rank"]),
            retrieval_score=float(payload["retrieval_score"]),
            trigger_evidence=tuple(payload.get("trigger_evidence", ())),
            required_preconditions=tuple(payload.get("required_preconditions", ())),
            recovery_operation=RecoveryOperation(str(payload["recovery_operation"])),
            target_object=(
                str(payload["target_object"]) if payload.get("target_object") is not None else None
            ),
            proposed_action=ProposedAction.from_mapping(proposed) if proposed else None,
            repair_targets=tuple(payload.get("repair_targets", ())),
            continuation_policy=ContinuationPolicy(str(payload["continuation_policy"])),
            success_evidence=tuple(payload.get("success_evidence", ())),
            stop_conditions=tuple(payload.get("stop_conditions", ())),
            source_tool=(
                str(payload["source_tool"]) if payload.get("source_tool") is not None else None
            ),
            extraction_confidence=float(payload["extraction_confidence"]),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "experience_id": self.experience_id,
            "natural_text": self.natural_text,
            "original_rank": self.original_rank,
            "retrieval_score": self.retrieval_score,
            "trigger_evidence": list(self.trigger_evidence),
            "required_preconditions": list(self.required_preconditions),
            "recovery_operation": self.recovery_operation.value,
            "target_object": self.target_object,
            "proposed_action": (
                self.proposed_action.to_mapping() if self.proposed_action else None
            ),
            "repair_targets": list(self.repair_targets),
            "continuation_policy": self.continuation_policy.value,
            "success_evidence": list(self.success_evidence),
            "stop_conditions": list(self.stop_conditions),
            "source_tool": self.source_tool,
            "extraction_confidence": self.extraction_confidence,
        }


@dataclass(frozen=True)
class CandidateEvaluation:
    experience_id: str
    original_rank: int
    eligible: bool
    contradictions: tuple[str, ...]
    precondition_status: TruthStatus
    compatibility: Compatibility
    repair_target_agreement: int
    trigger_evidence_agreement: int
    tool_compatibility: int
    extraction_confidence: float
    sort_key: tuple[int | float | str, ...]

    def to_mapping(self) -> dict[str, Any]:
        return {
            "experience_id": self.experience_id,
            "original_rank": self.original_rank,
            "eligible": self.eligible,
            "contradictions": list(self.contradictions),
            "precondition_status": self.precondition_status.value,
            "compatibility": self.compatibility.value,
            "repair_target_agreement": self.repair_target_agreement,
            "trigger_evidence_agreement": self.trigger_evidence_agreement,
            "tool_compatibility": self.tool_compatibility,
            "extraction_confidence": self.extraction_confidence,
            "sort_key": list(self.sort_key),
        }


@dataclass(frozen=True)
class SelectionDecision:
    rank1_experience_id: str
    selected_experience_id: str
    selected_original_rank: int
    selection_changed: bool
    abstained: bool
    reason_codes: tuple[str, ...]
    minimum_extraction_confidence: float
    candidate_evaluations: tuple[CandidateEvaluation, ...]
    method_version: str = "proper_v2_development"

    def __post_init__(self) -> None:
        if self.selection_changed != (
            self.selected_experience_id != self.rank1_experience_id
        ):
            raise ValueError("selection_changed is inconsistent with selected identity")
        if self.selection_changed and self.abstained:
            raise ValueError("an abstained decision cannot change Rank-1")
        if not self.reason_codes:
            raise ValueError("selection decision requires at least one reason code")

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "method_version": self.method_version,
            "rank1_experience_id": self.rank1_experience_id,
            "selected_experience_id": self.selected_experience_id,
            "selected_original_rank": self.selected_original_rank,
            "selection_changed": self.selection_changed,
            "abstained": self.abstained,
            "reason_codes": list(self.reason_codes),
            "minimum_extraction_confidence": self.minimum_extraction_confidence,
            "candidate_evaluations": [
                value.to_mapping() for value in self.candidate_evaluations
            ],
        }
