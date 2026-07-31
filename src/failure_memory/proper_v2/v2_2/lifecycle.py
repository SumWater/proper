"""Scenario-independent memory lifecycle for PROPER v2.2 development."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping, Sequence

from ..contracts import DecisionPhase, ProposedAction, RecoveryOperation


def _unique(values: Sequence[Any], field_name: str) -> tuple[str, ...]:
    normalized = tuple(sorted(str(value) for value in values))
    if any(not value for value in normalized):
        raise ValueError(f"{field_name} cannot contain empty strings")
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{field_name} must contain unique values")
    return normalized


class LifecycleStatus(str, Enum):
    ACTIVE = "active"
    CONSUMED = "consumed"
    FAILED = "failed"
    STOPPED = "stopped"


class TriggerStatus(str, Enum):
    HOLDS = "holds"
    CLEARED = "cleared"
    UNKNOWN = "unknown"


class EvidenceStatus(str, Enum):
    SATISFIED = "satisfied"
    VIOLATED = "violated"
    UNKNOWN = "unknown"


class PlanningMode(str, Enum):
    MEMORY_GUIDED = "memory_guided"
    ORDINARY_TASK_PLANNING = "ordinary_task_planning"
    STOPPED = "stopped"


class ExposureMode(str, Enum):
    FULL = "full"
    DEMOTED = "demoted"
    REMOVED = "removed"


@dataclass(frozen=True)
class LifecycleMemorySpec:
    """The runtime-verifiable subset of one selected memory card."""

    experience_id: str
    recovery_operation: RecoveryOperation
    proposed_action: ProposedAction | None
    trigger_evidence: tuple[str, ...]
    runtime_success_evidence: tuple[str, ...]
    declared_success_evidence: tuple[str, ...] = ()
    stop_conditions: tuple[str, ...] = ()
    natural_text: str = ""

    def __post_init__(self) -> None:
        if not self.experience_id:
            raise ValueError("lifecycle memory experience_id cannot be empty")
        for field_name in (
            "trigger_evidence",
            "runtime_success_evidence",
            "declared_success_evidence",
            "stop_conditions",
        ):
            object.__setattr__(
                self,
                field_name,
                _unique(getattr(self, field_name), field_name),
            )
        if not self.runtime_success_evidence:
            raise ValueError("runtime_success_evidence cannot be empty")
        if (
            self.recovery_operation
            in {
                RecoveryOperation.INVOKE_PREREQUISITE,
                RecoveryOperation.SWITCH_TOOL,
                RecoveryOperation.USE_FALLBACK,
            }
            and self.proposed_action is None
        ):
            raise ValueError(
                f"{self.recovery_operation.value} lifecycle requires a proposed action"
            )

    @classmethod
    def from_mapping(
        cls,
        payload: Mapping[str, Any],
        *,
        fallback_trigger_evidence: Sequence[str] = (),
    ) -> "LifecycleMemorySpec":
        operation = RecoveryOperation(str(payload["recovery_operation"]))
        proposed = payload.get("proposed_action")
        if proposed is not None and not isinstance(proposed, Mapping):
            raise ValueError("proposed_action must be an object or null")
        runtime_success = payload.get("runtime_success_evidence")
        if runtime_success is None:
            runtime_success = (
                ("agent_stopped",)
                if operation == RecoveryOperation.STOP_AND_REPORT
                else ("action_succeeded",)
                if proposed is not None
                else ("task_complete",)
            )
        trigger = payload.get("trigger_evidence", fallback_trigger_evidence)
        return cls(
            experience_id=str(payload["experience_id"]),
            recovery_operation=operation,
            proposed_action=ProposedAction.from_mapping(proposed) if proposed else None,
            trigger_evidence=tuple(trigger),
            runtime_success_evidence=tuple(runtime_success),
            declared_success_evidence=tuple(payload.get("success_evidence", ())),
            stop_conditions=tuple(payload.get("stop_conditions", ())),
            natural_text=str(payload.get("natural_text", "")),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "experience_id": self.experience_id,
            "recovery_operation": self.recovery_operation.value,
            "proposed_action": (
                self.proposed_action.to_mapping() if self.proposed_action else None
            ),
            "trigger_evidence": list(self.trigger_evidence),
            "runtime_success_evidence": list(self.runtime_success_evidence),
            "declared_success_evidence": list(self.declared_success_evidence),
            "stop_conditions": list(self.stop_conditions),
            "natural_text": self.natural_text,
        }


@dataclass(frozen=True)
class LifecyclePolicy:
    maximum_application_attempts: int = 2
    consumed_memory_weight: float = 0.0
    require_success_evidence: bool = True
    stop_on_success_trigger_conflict: bool = True

    def __post_init__(self) -> None:
        if self.maximum_application_attempts < 1:
            raise ValueError("maximum_application_attempts must be positive")
        if not 0.0 <= self.consumed_memory_weight < 1.0:
            raise ValueError("consumed_memory_weight must be in [0, 1)")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "LifecyclePolicy":
        return cls(
            maximum_application_attempts=int(
                payload["maximum_application_attempts"]
            ),
            consumed_memory_weight=float(payload["consumed_memory_weight"]),
            require_success_evidence=bool(payload["require_success_evidence"]),
            stop_on_success_trigger_conflict=bool(
                payload["stop_on_success_trigger_conflict"]
            ),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "maximum_application_attempts": self.maximum_application_attempts,
            "consumed_memory_weight": self.consumed_memory_weight,
            "require_success_evidence": self.require_success_evidence,
            "stop_on_success_trigger_conflict": (
                self.stop_on_success_trigger_conflict
            ),
        }


@dataclass(frozen=True)
class LifecycleObservation:
    """Public evidence available at one lifecycle transition."""

    phase: DecisionPhase
    active_trigger_evidence: tuple[str, ...] = ()
    cleared_trigger_evidence: tuple[str, ...] = ()
    evidence_codes: tuple[str, ...] = ()
    action: ProposedAction | None = None
    action_succeeded: bool | None = None
    agent_stop_reason: str | None = None
    task_complete: bool = False

    def __post_init__(self) -> None:
        for field_name in (
            "active_trigger_evidence",
            "cleared_trigger_evidence",
            "evidence_codes",
        ):
            object.__setattr__(
                self,
                field_name,
                _unique(getattr(self, field_name), field_name),
            )
        overlap = set(self.active_trigger_evidence) & set(
            self.cleared_trigger_evidence
        )
        if overlap:
            raise ValueError(
                "trigger evidence cannot be active and cleared: "
                f"{sorted(overlap)}"
            )
        if self.action_succeeded is not None and self.action is None:
            raise ValueError("action_succeeded requires an observed action")
        if self.agent_stop_reason == "":
            raise ValueError("agent_stop_reason cannot be empty")

    def to_mapping(self) -> dict[str, Any]:
        return {
            "phase": self.phase.value,
            "active_trigger_evidence": list(self.active_trigger_evidence),
            "cleared_trigger_evidence": list(self.cleared_trigger_evidence),
            "evidence_codes": list(self.evidence_codes),
            "action": self.action.to_mapping() if self.action else None,
            "action_succeeded": self.action_succeeded,
            "agent_stop_reason": self.agent_stop_reason,
            "task_complete": self.task_complete,
        }


@dataclass(frozen=True)
class LifecycleState:
    memory_experience_id: str
    phase: DecisionPhase
    status: LifecycleStatus
    trigger_status: TriggerStatus
    success_evidence_status: EvidenceStatus
    planning_mode: PlanningMode
    exposure_mode: ExposureMode
    injection_weight: float
    application_attempt_count: int
    failed_attempt_count: int
    remaining_application_attempts: int
    transition_index: int
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.memory_experience_id:
            raise ValueError("memory_experience_id cannot be empty")
        if min(
            self.application_attempt_count,
            self.failed_attempt_count,
            self.remaining_application_attempts,
            self.transition_index,
        ) < 0:
            raise ValueError("lifecycle counters cannot be negative")
        if not 0.0 <= self.injection_weight <= 1.0:
            raise ValueError("injection_weight must be in [0, 1]")
        object.__setattr__(
            self,
            "reason_codes",
            _unique(self.reason_codes, "reason_codes"),
        )
        if not self.reason_codes:
            raise ValueError("lifecycle state requires a reason code")
        if self.status == LifecycleStatus.ACTIVE:
            if self.planning_mode != PlanningMode.MEMORY_GUIDED:
                raise ValueError("active lifecycle must be memory-guided")
            if self.exposure_mode != ExposureMode.FULL:
                raise ValueError("active lifecycle requires full exposure")
            if self.injection_weight != 1.0:
                raise ValueError("active lifecycle requires weight 1")
        if self.status == LifecycleStatus.CONSUMED:
            if self.planning_mode != PlanningMode.ORDINARY_TASK_PLANNING:
                raise ValueError("consumed lifecycle must return to ordinary planning")
        if self.status in {LifecycleStatus.FAILED, LifecycleStatus.STOPPED}:
            if self.planning_mode != PlanningMode.STOPPED:
                raise ValueError("failed or stopped lifecycle must stop planning")

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "method_version": "proper_v2_2_development",
            "memory_experience_id": self.memory_experience_id,
            "phase": self.phase.value,
            "status": self.status.value,
            "trigger_status": self.trigger_status.value,
            "success_evidence_status": self.success_evidence_status.value,
            "planning_mode": self.planning_mode.value,
            "exposure_mode": self.exposure_mode.value,
            "injection_weight": self.injection_weight,
            "application_attempt_count": self.application_attempt_count,
            "failed_attempt_count": self.failed_attempt_count,
            "remaining_application_attempts": self.remaining_application_attempts,
            "transition_index": self.transition_index,
            "reason_codes": list(self.reason_codes),
        }


def _same_action(left: ProposedAction | None, right: ProposedAction | None) -> bool:
    return (
        left is not None
        and right is not None
        and left.tool_name == right.tool_name
        and dict(left.argument_template) == dict(right.argument_template)
    )


def _trigger_status(
    memory: LifecycleMemorySpec,
    observation: LifecycleObservation,
) -> TriggerStatus:
    required = set(memory.trigger_evidence)
    if not required:
        return TriggerStatus.UNKNOWN
    if required & set(observation.active_trigger_evidence):
        return TriggerStatus.HOLDS
    if required.issubset(set(observation.cleared_trigger_evidence)):
        return TriggerStatus.CLEARED
    return TriggerStatus.UNKNOWN


def _observed_evidence(
    memory: LifecycleMemorySpec,
    observation: LifecycleObservation,
) -> set[str]:
    found = set(observation.evidence_codes)
    if observation.agent_stop_reason is not None:
        found.add("agent_stopped")
        found.add(f"agent_stop:{observation.agent_stop_reason}")
    if observation.task_complete:
        found.add("task_complete")
    if _same_action(memory.proposed_action, observation.action):
        if observation.action_succeeded is True:
            found.add("action_succeeded")
        elif observation.action_succeeded is False:
            found.add("action_failed")
    return found


def _success_status(
    memory: LifecycleMemorySpec,
    observation: LifecycleObservation,
) -> EvidenceStatus:
    evidence = _observed_evidence(memory, observation)
    if set(memory.runtime_success_evidence) & evidence:
        return EvidenceStatus.SATISFIED
    if "action_failed" in evidence:
        return EvidenceStatus.VIOLATED
    return EvidenceStatus.UNKNOWN


def _terminal_exposure(
    policy: LifecyclePolicy,
    status: LifecycleStatus,
) -> tuple[ExposureMode, float]:
    if status == LifecycleStatus.CONSUMED and policy.consumed_memory_weight > 0:
        return ExposureMode.DEMOTED, policy.consumed_memory_weight
    return ExposureMode.REMOVED, 0.0


def start_lifecycle(
    memory: LifecycleMemorySpec,
    observation: LifecycleObservation,
    policy: LifecyclePolicy,
) -> LifecycleState:
    trigger = _trigger_status(memory, observation)
    if trigger == TriggerStatus.CLEARED:
        exposure, weight = _terminal_exposure(policy, LifecycleStatus.CONSUMED)
        return LifecycleState(
            memory_experience_id=memory.experience_id,
            phase=observation.phase,
            status=LifecycleStatus.CONSUMED,
            trigger_status=trigger,
            success_evidence_status=EvidenceStatus.UNKNOWN,
            planning_mode=PlanningMode.ORDINARY_TASK_PLANNING,
            exposure_mode=exposure,
            injection_weight=weight,
            application_attempt_count=0,
            failed_attempt_count=0,
            remaining_application_attempts=policy.maximum_application_attempts,
            transition_index=0,
            reason_codes=("trigger_already_cleared",),
        )
    return LifecycleState(
        memory_experience_id=memory.experience_id,
        phase=observation.phase,
        status=LifecycleStatus.ACTIVE,
        trigger_status=trigger,
        success_evidence_status=EvidenceStatus.UNKNOWN,
        planning_mode=PlanningMode.MEMORY_GUIDED,
        exposure_mode=ExposureMode.FULL,
        injection_weight=1.0,
        application_attempt_count=0,
        failed_attempt_count=0,
        remaining_application_attempts=policy.maximum_application_attempts,
        transition_index=0,
        reason_codes=(
            (
                "trigger_holds_memory_active"
                if trigger == TriggerStatus.HOLDS
                else "trigger_unknown_memory_active_conservatively"
            ),
        ),
    )


def advance_lifecycle(
    state: LifecycleState,
    memory: LifecycleMemorySpec,
    observation: LifecycleObservation,
    policy: LifecyclePolicy,
) -> LifecycleState:
    if state.memory_experience_id != memory.experience_id:
        raise ValueError("lifecycle state and memory identity differ")
    if state.phase != observation.phase:
        raise ValueError("lifecycle phase cannot change within one branch")
    if state.status != LifecycleStatus.ACTIVE:
        return replace(
            state,
            transition_index=state.transition_index + 1,
            reason_codes=("terminal_state_is_stable",),
        )

    trigger = _trigger_status(memory, observation)
    success = _success_status(memory, observation)
    evidence = _observed_evidence(memory, observation)
    attempts = state.application_attempt_count
    failures = state.failed_attempt_count
    if _same_action(memory.proposed_action, observation.action):
        attempts += 1
        if observation.action_succeeded is False:
            failures += 1
    remaining = max(0, policy.maximum_application_attempts - attempts)

    if observation.task_complete:
        status = LifecycleStatus.STOPPED
        reason = "task_complete"
    elif observation.agent_stop_reason is not None:
        status = LifecycleStatus.STOPPED
        reason = "agent_stopped"
    elif set(memory.stop_conditions) & evidence:
        status = LifecycleStatus.STOPPED
        reason = "memory_stop_condition_observed"
    elif trigger == TriggerStatus.CLEARED:
        status = LifecycleStatus.CONSUMED
        reason = "trigger_cleared_memory_consumed"
    elif success == EvidenceStatus.SATISFIED:
        if (
            trigger == TriggerStatus.HOLDS
            and policy.stop_on_success_trigger_conflict
        ):
            status = LifecycleStatus.FAILED
            reason = "success_evidence_conflicts_with_active_trigger"
        else:
            status = LifecycleStatus.CONSUMED
            reason = "success_evidence_verified_memory_consumed"
    elif success == EvidenceStatus.VIOLATED:
        if remaining == 0:
            status = LifecycleStatus.FAILED
            reason = "application_retry_budget_exhausted"
        else:
            status = LifecycleStatus.ACTIVE
            reason = "application_failed_retry_budget_remains"
    elif (
        _same_action(memory.proposed_action, observation.action)
        and observation.action_succeeded is True
        and policy.require_success_evidence
    ):
        status = LifecycleStatus.FAILED
        reason = "successful_action_lacks_required_success_evidence"
    else:
        status = LifecycleStatus.ACTIVE
        reason = "no_terminal_lifecycle_evidence"

    if status == LifecycleStatus.ACTIVE:
        planning = PlanningMode.MEMORY_GUIDED
        exposure = ExposureMode.FULL
        weight = 1.0
    elif status == LifecycleStatus.CONSUMED:
        planning = PlanningMode.ORDINARY_TASK_PLANNING
        exposure, weight = _terminal_exposure(policy, status)
    else:
        planning = PlanningMode.STOPPED
        exposure, weight = _terminal_exposure(policy, status)
    return LifecycleState(
        memory_experience_id=state.memory_experience_id,
        phase=state.phase,
        status=status,
        trigger_status=trigger,
        success_evidence_status=success,
        planning_mode=planning,
        exposure_mode=exposure,
        injection_weight=weight,
        application_attempt_count=attempts,
        failed_attempt_count=failures,
        remaining_application_attempts=remaining,
        transition_index=state.transition_index + 1,
        reason_codes=(reason,),
    )


def guard_decision(
    state: LifecycleState,
    memory: LifecycleMemorySpec,
    decision: Mapping[str, Any],
) -> tuple[bool, str]:
    """Prevent terminal-state tool calls and repeated consumed recovery actions."""

    kind = str(decision.get("kind", ""))
    if kind == "stop":
        return True, "stop_decision_allowed"
    if kind != "tool":
        return False, "invalid_decision_kind"
    proposed = ProposedAction(
        tool_name=str(decision.get("tool_name", "")),
        argument_template=(
            decision.get("arguments")
            if isinstance(decision.get("arguments"), Mapping)
            else {}
        ),
    )
    repeats_memory = _same_action(memory.proposed_action, proposed)
    if state.status == LifecycleStatus.CONSUMED and repeats_memory:
        return False, "consumed_memory_action_repeat_blocked"
    if state.status in {LifecycleStatus.FAILED, LifecycleStatus.STOPPED}:
        return False, "terminal_lifecycle_tool_call_blocked"
    if (
        state.status == LifecycleStatus.ACTIVE
        and memory.recovery_operation == RecoveryOperation.STOP_AND_REPORT
    ):
        return False, "active_stop_policy_tool_call_blocked"
    return True, "tool_decision_allowed"


def lifecycle_prompt_payload(
    state: LifecycleState,
    memory: LifecycleMemorySpec,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "lifecycle": state.to_mapping(),
        "planning_instruction": (
            "Apply the active memory once, then wait for visible success evidence."
            if state.planning_mode == PlanningMode.MEMORY_GUIDED
            else "Resume ordinary planning for the original task using visible state."
            if state.planning_mode == PlanningMode.ORDINARY_TASK_PLANNING
            else "Do not make another tool call; report the stop reason."
        ),
        "memory": None,
    }
    if state.exposure_mode == ExposureMode.FULL:
        payload["memory"] = memory.to_mapping()
    elif state.exposure_mode == ExposureMode.DEMOTED:
        payload["memory"] = {
            "experience_id": memory.experience_id,
            "status": state.status.value,
            "weight": state.injection_weight,
            "actionable_content_removed": True,
        }
    return payload
