"""Observable execution contracts for PROPER v2.3 development."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence

from ..contracts import DecisionPhase, RecoveryOperation, RetrySafety
from ..v2_2 import LifecycleStatus, PlanningMode


def _unique(values: Sequence[Any], field_name: str) -> tuple[str, ...]:
    normalized = tuple(sorted(str(value) for value in values))
    if any(not value for value in normalized):
        raise ValueError(f"{field_name} cannot contain empty strings")
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{field_name} must contain unique values")
    return normalized


def _normalize_json(value: Any, path: str = "$") -> Any:
    """Return a deterministic JSON-compatible value without semantic guessing."""

    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, child in value.items():
            name = str(key)
            if not name:
                raise ValueError(f"empty argument key at {path}")
            if name in normalized:
                raise ValueError(f"argument keys collide after normalization at {path}.{name}")
            normalized[name] = _normalize_json(child, f"{path}.{name}")
        return {key: normalized[key] for key in sorted(normalized)}
    if isinstance(value, (list, tuple)):
        return [_normalize_json(child, f"{path}[{index}]") for index, child in enumerate(value)]
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"non-finite argument number at {path}")
        return value
    raise ValueError(f"unsupported argument value at {path}: {type(value).__name__}")


class ActionEffectClass(str, Enum):
    READ_ONLY = "read_only"
    IDEMPOTENT_STATE_SETTING = "idempotent_state_setting"
    NON_IDEMPOTENT_SIDE_EFFECT = "non_idempotent_side_effect"
    UNKNOWN_EFFECT = "unknown_effect"


class ExecutionStatus(str, Enum):
    PROPOSED = "proposed"
    EXECUTED = "executed"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    OUTCOME_UNKNOWN = "outcome_unknown"


class ActionPurpose(str, Enum):
    RECOVERY = "recovery"
    ORDINARY_TASK = "ordinary_task"
    VERIFICATION = "verification"


class EvidenceSource(str, Enum):
    TOOL_SCHEMA = "tool_schema"
    PUBLIC_ENVIRONMENT_CONTRACT = "public_environment_contract"
    TOOL_RESULT = "tool_result"
    PUBLIC_STATE = "public_state"
    AGENT_DECISION = "agent_decision"
    CONTROLLER = "controller"


class ControllerDisposition(str, Enum):
    ALLOW = "allow"
    VERIFY = "verify"
    REPLAN = "replan"
    STOP = "stop"


@dataclass(frozen=True)
class ActionSpec:
    tool_name: str
    arguments: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not self.tool_name:
            raise ValueError("action tool_name cannot be empty")
        normalized = _normalize_json(self.arguments, "$.arguments")
        if not isinstance(normalized, dict):
            raise ValueError("action arguments must be an object")
        object.__setattr__(self, "arguments", normalized)

    @property
    def canonical_json(self) -> str:
        return json.dumps(
            {"arguments": self.arguments, "tool_name": self.tool_name},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    @property
    def identity(self) -> str:
        return hashlib.sha256(self.canonical_json.encode("utf-8")).hexdigest()

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ActionSpec":
        arguments = payload.get("arguments")
        if not isinstance(arguments, Mapping):
            raise ValueError("action arguments must be an object")
        return cls(tool_name=str(payload["tool_name"]), arguments=arguments)

    def to_mapping(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "arguments": dict(self.arguments),
            "normalized_identity": self.identity,
        }


@dataclass(frozen=True)
class ActionEffectContract:
    effect_class: ActionEffectClass
    classification_evidence: tuple[str, ...]
    retry_safety: RetrySafety
    retry_safety_evidence: tuple[str, ...] = ()
    verification_supported: bool = False
    verification_evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.effect_class, ActionEffectClass):
            raise ValueError("effect_class must be an ActionEffectClass")
        if not isinstance(self.retry_safety, RetrySafety):
            raise ValueError("retry_safety must be a RetrySafety")
        for field_name in (
            "classification_evidence",
            "retry_safety_evidence",
            "verification_evidence",
        ):
            object.__setattr__(
                self,
                field_name,
                _unique(getattr(self, field_name), field_name),
            )
        if not self.classification_evidence:
            raise ValueError("effect classification requires public evidence")
        if self.retry_safety != RetrySafety.UNKNOWN and not self.retry_safety_evidence:
            raise ValueError("known retry safety requires public evidence")
        if self.verification_supported and not self.verification_evidence:
            raise ValueError("supported verification requires public evidence")
        if not self.verification_supported and self.verification_evidence:
            raise ValueError("verification evidence requires verification_supported=true")

    def to_mapping(self) -> dict[str, Any]:
        return {
            "effect_class": self.effect_class.value,
            "classification_evidence": list(self.classification_evidence),
            "retry_safety": self.retry_safety.value,
            "retry_safety_evidence": list(self.retry_safety_evidence),
            "verification_supported": self.verification_supported,
            "verification_evidence": list(self.verification_evidence),
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ActionEffectContract":
        verification_supported = payload.get("verification_supported", False)
        if not isinstance(verification_supported, bool):
            raise ValueError("verification_supported must be boolean")
        return cls(
            effect_class=ActionEffectClass(str(payload["effect_class"])),
            classification_evidence=tuple(
                payload.get("classification_evidence", ())
            ),
            retry_safety=RetrySafety(str(payload["retry_safety"])),
            retry_safety_evidence=tuple(
                payload.get("retry_safety_evidence", ())
            ),
            verification_supported=verification_supported,
            verification_evidence=tuple(
                payload.get("verification_evidence", ())
            ),
        )


@dataclass(frozen=True)
class EvidenceRecord:
    source: EvidenceSource
    code: str
    observed_at_step: int

    def __post_init__(self) -> None:
        if not isinstance(self.source, EvidenceSource):
            raise ValueError("evidence source must be an EvidenceSource")
        if not self.code:
            raise ValueError("evidence code cannot be empty")
        if self.observed_at_step < 0:
            raise ValueError("observed_at_step cannot be negative")

    def to_mapping(self) -> dict[str, Any]:
        return {
            "source": self.source.value,
            "code": self.code,
            "observed_at_step": self.observed_at_step,
        }


@dataclass(frozen=True)
class BudgetPolicy:
    maximum_retries: int = 1
    maximum_verifications: int = 2
    maximum_invalid_decisions: int = 1
    maximum_replans: int = 2

    def __post_init__(self) -> None:
        for field_name in (
            "maximum_retries",
            "maximum_verifications",
            "maximum_invalid_decisions",
            "maximum_replans",
        ):
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name} cannot be negative")

    def initial_state(self) -> "BudgetState":
        return BudgetState(
            remaining_retries=self.maximum_retries,
            remaining_verifications=self.maximum_verifications,
            remaining_invalid_decisions=self.maximum_invalid_decisions,
            remaining_replans=self.maximum_replans,
        )

    def to_mapping(self) -> dict[str, int]:
        return {
            "maximum_retries": self.maximum_retries,
            "maximum_verifications": self.maximum_verifications,
            "maximum_invalid_decisions": self.maximum_invalid_decisions,
            "maximum_replans": self.maximum_replans,
        }


@dataclass(frozen=True)
class BudgetState:
    remaining_retries: int
    remaining_verifications: int
    remaining_invalid_decisions: int
    remaining_replans: int

    def __post_init__(self) -> None:
        if min(
            self.remaining_retries,
            self.remaining_verifications,
            self.remaining_invalid_decisions,
            self.remaining_replans,
        ) < 0:
            raise ValueError("remaining budgets cannot be negative")

    def to_mapping(self) -> dict[str, int]:
        return {
            "remaining_retries": self.remaining_retries,
            "remaining_verifications": self.remaining_verifications,
            "remaining_invalid_decisions": self.remaining_invalid_decisions,
            "remaining_replans": self.remaining_replans,
        }


@dataclass(frozen=True)
class ControllerState:
    phase: DecisionPhase
    selected_memory_experience_id: str
    memory_operation: RecoveryOperation
    memory_action_identity: str | None
    lifecycle_status: LifecycleStatus
    planning_mode: PlanningMode
    budgets: BudgetState
    transition_index: int = 0
    verification_required_for_entry_id: str | None = None
    stop_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.selected_memory_experience_id:
            raise ValueError("selected_memory_experience_id cannot be empty")
        if self.transition_index < 0:
            raise ValueError("transition_index cannot be negative")
        if self.lifecycle_status == LifecycleStatus.ACTIVE:
            if self.planning_mode != PlanningMode.MEMORY_GUIDED:
                raise ValueError("active lifecycle must be memory-guided")
        elif self.lifecycle_status == LifecycleStatus.CONSUMED:
            if self.planning_mode != PlanningMode.ORDINARY_TASK_PLANNING:
                raise ValueError("consumed lifecycle must use ordinary planning")
        else:
            if self.planning_mode != PlanningMode.STOPPED:
                raise ValueError("failed or stopped lifecycle must stop planning")
        terminal = self.lifecycle_status in {
            LifecycleStatus.FAILED,
            LifecycleStatus.STOPPED,
        }
        if terminal and not self.stop_reason:
            raise ValueError("terminal controller state requires a stop reason")
        if not terminal and self.stop_reason is not None:
            raise ValueError("non-terminal controller state cannot have a stop reason")

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "method_version": "proper_v2_3_execution_controller_development",
            "phase": self.phase.value,
            "selected_memory_experience_id": self.selected_memory_experience_id,
            "memory_operation": self.memory_operation.value,
            "memory_action_identity": self.memory_action_identity,
            "lifecycle_status": self.lifecycle_status.value,
            "planning_mode": self.planning_mode.value,
            "budgets": self.budgets.to_mapping(),
            "transition_index": self.transition_index,
            "verification_required_for_entry_id": (
                self.verification_required_for_entry_id
            ),
            "stop_reason": self.stop_reason,
        }


@dataclass(frozen=True)
class ControllerDecision:
    disposition: ControllerDisposition
    decision_allowed: bool
    reason_code: str
    ledger_entry_id: str | None
    state: ControllerState

    def __post_init__(self) -> None:
        if not self.reason_code:
            raise ValueError("controller decision requires a reason_code")
        if self.disposition == ControllerDisposition.STOP and self.decision_allowed:
            raise ValueError("stop disposition cannot allow a tool action")
        if self.disposition == ControllerDisposition.REPLAN and self.decision_allowed:
            raise ValueError("replan disposition cannot allow the blocked proposal")

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "method_version": "proper_v2_3_execution_controller_development",
            "disposition": self.disposition.value,
            "decision_allowed": self.decision_allowed,
            "reason_code": self.reason_code,
            "ledger_entry_id": self.ledger_entry_id,
            "state": self.state.to_mapping(),
        }
