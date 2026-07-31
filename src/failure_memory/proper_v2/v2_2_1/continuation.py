"""Scenario-independent continuation control after memory consumption.

This module extends the frozen v2.2 lifecycle without changing it.  It keeps
successful recovery actions in a non-actionable execution ledger, blocks an
exact consumed-action repeat, and gives the ordinary planner a bounded chance
to replan instead of immediately terminating the original task.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping, Sequence

from ..contracts import ProposedAction
from ..v2_2 import (
    LifecycleMemorySpec,
    LifecycleState,
    LifecycleStatus,
    PlanningMode,
    guard_decision,
)


def _unique(values: Sequence[Any], field_name: str) -> tuple[str, ...]:
    normalized = tuple(sorted(str(value) for value in values))
    if any(not value for value in normalized):
        raise ValueError(f"{field_name} cannot contain empty strings")
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{field_name} must contain unique values")
    return normalized


def _action_from_decision(decision: Mapping[str, Any]) -> ProposedAction | None:
    if str(decision.get("kind", "")) != "tool":
        return None
    arguments = decision.get("arguments")
    if not isinstance(arguments, Mapping):
        arguments = {}
    return ProposedAction(
        tool_name=str(decision.get("tool_name", "")),
        argument_template=dict(arguments),
    )


def _same_action(left: ProposedAction | None, right: ProposedAction | None) -> bool:
    return (
        left is not None
        and right is not None
        and left.tool_name == right.tool_name
        and dict(left.argument_template) == dict(right.argument_template)
    )


class ContinuationMode(str, Enum):
    MEMORY_GUIDED = "memory_guided"
    ORDINARY_TASK_PLANNING = "ordinary_task_planning"
    REPLAN_REQUIRED = "replan_required"
    STOPPED = "stopped"


class ReviewDisposition(str, Enum):
    ALLOW = "allow"
    REPLAN = "replan"
    STOP = "stop"


@dataclass(frozen=True)
class CompletedAction:
    """Non-actionable evidence that one exact action already succeeded."""

    action: ProposedAction
    success_evidence: tuple[str, ...]
    lifecycle_transition_index: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "success_evidence",
            _unique(self.success_evidence, "success_evidence"),
        )
        if not self.success_evidence:
            raise ValueError("completed action requires success evidence")
        if self.lifecycle_transition_index < 0:
            raise ValueError("lifecycle_transition_index cannot be negative")

    def to_mapping(self) -> dict[str, Any]:
        return {
            "action": self.action.to_mapping(),
            "success_evidence": list(self.success_evidence),
            "lifecycle_transition_index": self.lifecycle_transition_index,
        }


@dataclass(frozen=True)
class ContinuationPolicy:
    maximum_repeat_replans: int = 2
    maximum_invalid_replans: int = 1
    require_completed_action_evidence: bool = True

    def __post_init__(self) -> None:
        if self.maximum_repeat_replans < 0:
            raise ValueError("maximum_repeat_replans cannot be negative")
        if self.maximum_invalid_replans < 0:
            raise ValueError("maximum_invalid_replans cannot be negative")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ContinuationPolicy":
        return cls(
            maximum_repeat_replans=int(payload["maximum_repeat_replans"]),
            maximum_invalid_replans=int(payload["maximum_invalid_replans"]),
            require_completed_action_evidence=bool(
                payload["require_completed_action_evidence"]
            ),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "maximum_repeat_replans": self.maximum_repeat_replans,
            "maximum_invalid_replans": self.maximum_invalid_replans,
            "require_completed_action_evidence": (
                self.require_completed_action_evidence
            ),
        }


@dataclass(frozen=True)
class ContinuationState:
    memory_experience_id: str
    lifecycle_status: LifecycleStatus
    lifecycle_transition_index: int
    mode: ContinuationMode
    completed_actions: tuple[CompletedAction, ...]
    blocked_repeat_count: int
    invalid_decision_count: int
    replan_count: int
    remaining_repeat_replans: int
    remaining_invalid_replans: int
    transition_index: int
    feedback_codes: tuple[str, ...]
    stop_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.memory_experience_id:
            raise ValueError("memory_experience_id cannot be empty")
        if min(
            self.lifecycle_transition_index,
            self.blocked_repeat_count,
            self.invalid_decision_count,
            self.replan_count,
            self.remaining_repeat_replans,
            self.remaining_invalid_replans,
            self.transition_index,
        ) < 0:
            raise ValueError("continuation counters cannot be negative")
        object.__setattr__(
            self,
            "feedback_codes",
            _unique(self.feedback_codes, "feedback_codes"),
        )
        if self.mode == ContinuationMode.REPLAN_REQUIRED:
            if not self.feedback_codes:
                raise ValueError("replan state requires feedback codes")
            if self.stop_reason is not None:
                raise ValueError("replan state cannot carry a stop reason")
        if self.mode == ContinuationMode.STOPPED:
            if not self.stop_reason:
                raise ValueError("stopped continuation requires a stop reason")
        elif self.stop_reason is not None:
            raise ValueError("non-stopped continuation cannot carry a stop reason")

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "method_version": "proper_v2_2_1_continuation_development",
            "memory_experience_id": self.memory_experience_id,
            "lifecycle_status": self.lifecycle_status.value,
            "lifecycle_transition_index": self.lifecycle_transition_index,
            "mode": self.mode.value,
            "completed_actions": [
                item.to_mapping() for item in self.completed_actions
            ],
            "blocked_repeat_count": self.blocked_repeat_count,
            "invalid_decision_count": self.invalid_decision_count,
            "replan_count": self.replan_count,
            "remaining_repeat_replans": self.remaining_repeat_replans,
            "remaining_invalid_replans": self.remaining_invalid_replans,
            "transition_index": self.transition_index,
            "feedback_codes": list(self.feedback_codes),
            "stop_reason": self.stop_reason,
        }


@dataclass(frozen=True)
class ContinuationReview:
    disposition: ReviewDisposition
    reason_code: str
    decision_allowed: bool
    state: ContinuationState

    def to_mapping(self) -> dict[str, Any]:
        return {
            "disposition": self.disposition.value,
            "reason_code": self.reason_code,
            "decision_allowed": self.decision_allowed,
            "state": self.state.to_mapping(),
        }


def initial_continuation_state(
    lifecycle_state: LifecycleState,
    policy: ContinuationPolicy,
) -> ContinuationState:
    if lifecycle_state.planning_mode == PlanningMode.MEMORY_GUIDED:
        mode = ContinuationMode.MEMORY_GUIDED
    elif lifecycle_state.planning_mode == PlanningMode.ORDINARY_TASK_PLANNING:
        mode = ContinuationMode.ORDINARY_TASK_PLANNING
    else:
        mode = ContinuationMode.STOPPED
    return ContinuationState(
        memory_experience_id=lifecycle_state.memory_experience_id,
        lifecycle_status=lifecycle_state.status,
        lifecycle_transition_index=lifecycle_state.transition_index,
        mode=mode,
        completed_actions=(),
        blocked_repeat_count=0,
        invalid_decision_count=0,
        replan_count=0,
        remaining_repeat_replans=policy.maximum_repeat_replans,
        remaining_invalid_replans=policy.maximum_invalid_replans,
        transition_index=0,
        feedback_codes=(),
        stop_reason=(
            "terminal_lifecycle"
            if mode == ContinuationMode.STOPPED
            else None
        ),
    )


def record_completed_action(
    state: ContinuationState,
    *,
    lifecycle_state: LifecycleState,
    action: ProposedAction,
    success_evidence: Sequence[str],
) -> ContinuationState:
    if lifecycle_state.memory_experience_id != state.memory_experience_id:
        raise ValueError("continuation and lifecycle memory identity differ")
    if lifecycle_state.status != LifecycleStatus.CONSUMED:
        raise ValueError(
            "completed recovery action requires a consumed lifecycle"
        )
    evidence = _unique(success_evidence, "success_evidence")
    if not evidence:
        raise ValueError("completed action requires success evidence")
    entries = list(state.completed_actions)
    if not any(_same_action(item.action, action) for item in entries):
        entries.append(
            CompletedAction(
                action=action,
                success_evidence=evidence,
                lifecycle_transition_index=lifecycle_state.transition_index,
            )
        )
    if lifecycle_state.planning_mode == PlanningMode.ORDINARY_TASK_PLANNING:
        mode = ContinuationMode.ORDINARY_TASK_PLANNING
        stop_reason = None
    elif lifecycle_state.planning_mode == PlanningMode.MEMORY_GUIDED:
        mode = ContinuationMode.MEMORY_GUIDED
        stop_reason = None
    else:
        mode = ContinuationMode.STOPPED
        stop_reason = "terminal_lifecycle"
    return replace(
        state,
        lifecycle_status=lifecycle_state.status,
        lifecycle_transition_index=lifecycle_state.transition_index,
        mode=mode,
        completed_actions=tuple(entries),
        transition_index=state.transition_index + 1,
        feedback_codes=(),
        stop_reason=stop_reason,
    )


def _stop_review(
    state: ContinuationState,
    reason: str,
) -> ContinuationReview:
    stopped = replace(
        state,
        mode=ContinuationMode.STOPPED,
        transition_index=state.transition_index + 1,
        feedback_codes=(reason,),
        stop_reason=reason,
    )
    return ContinuationReview(
        disposition=ReviewDisposition.STOP,
        reason_code=reason,
        decision_allowed=False,
        state=stopped,
    )


def review_decision(
    state: ContinuationState,
    lifecycle_state: LifecycleState,
    memory: LifecycleMemorySpec,
    decision: Mapping[str, Any],
    policy: ContinuationPolicy,
) -> ContinuationReview:
    """Review one proposed decision without executing a blocked tool action."""

    if lifecycle_state.memory_experience_id != state.memory_experience_id:
        raise ValueError("continuation and lifecycle memory identity differ")
    if state.mode == ContinuationMode.STOPPED:
        return _stop_review(state, state.stop_reason or "continuation_stopped")

    kind = str(decision.get("kind", ""))
    if kind == "stop":
        reason = str(decision.get("reason_code", "agent_stopped"))
        stopped = replace(
            state,
            lifecycle_status=lifecycle_state.status,
            lifecycle_transition_index=lifecycle_state.transition_index,
            mode=ContinuationMode.STOPPED,
            transition_index=state.transition_index + 1,
            feedback_codes=(),
            stop_reason=reason,
        )
        return ContinuationReview(
            disposition=ReviewDisposition.ALLOW,
            reason_code="stop_decision_allowed",
            decision_allowed=True,
            state=stopped,
        )

    if kind != "tool":
        if state.remaining_invalid_replans == 0:
            return _stop_review(state, "invalid_replan_budget_exhausted")
        replanning = replace(
            state,
            lifecycle_status=lifecycle_state.status,
            lifecycle_transition_index=lifecycle_state.transition_index,
            mode=ContinuationMode.REPLAN_REQUIRED,
            invalid_decision_count=state.invalid_decision_count + 1,
            replan_count=state.replan_count + 1,
            remaining_invalid_replans=state.remaining_invalid_replans - 1,
            transition_index=state.transition_index + 1,
            feedback_codes=(
                "invalid_decision_blocked",
                "return_one_valid_next_decision",
            ),
            stop_reason=None,
        )
        return ContinuationReview(
            disposition=ReviewDisposition.REPLAN,
            reason_code="invalid_decision_replan_required",
            decision_allowed=False,
            state=replanning,
        )

    allowed, lifecycle_reason = guard_decision(
        lifecycle_state,
        memory,
        decision,
    )
    proposed = _action_from_decision(decision)
    repeats_completed = any(
        _same_action(item.action, proposed) for item in state.completed_actions
    )
    consumed_repeat = (
        lifecycle_state.status == LifecycleStatus.CONSUMED
        and (
            lifecycle_reason == "consumed_memory_action_repeat_blocked"
            or repeats_completed
        )
    )
    if consumed_repeat:
        if (
            policy.require_completed_action_evidence
            and not state.completed_actions
        ):
            return _stop_review(
                state,
                "consumed_repeat_lacks_completed_action_evidence",
            )
        if state.remaining_repeat_replans == 0:
            return _stop_review(state, "repeat_replan_budget_exhausted")
        replanning = replace(
            state,
            lifecycle_status=lifecycle_state.status,
            lifecycle_transition_index=lifecycle_state.transition_index,
            mode=ContinuationMode.REPLAN_REQUIRED,
            blocked_repeat_count=state.blocked_repeat_count + 1,
            replan_count=state.replan_count + 1,
            remaining_repeat_replans=state.remaining_repeat_replans - 1,
            transition_index=state.transition_index + 1,
            feedback_codes=(
                "completed_action_repeat_blocked",
                "continue_original_task",
                "select_uncompleted_next_step",
            ),
            stop_reason=None,
        )
        return ContinuationReview(
            disposition=ReviewDisposition.REPLAN,
            reason_code="consumed_action_repeat_replan_required",
            decision_allowed=False,
            state=replanning,
        )
    if not allowed:
        return _stop_review(state, lifecycle_reason)

    if lifecycle_state.planning_mode == PlanningMode.MEMORY_GUIDED:
        mode = ContinuationMode.MEMORY_GUIDED
    else:
        mode = ContinuationMode.ORDINARY_TASK_PLANNING
    accepted = replace(
        state,
        lifecycle_status=lifecycle_state.status,
        lifecycle_transition_index=lifecycle_state.transition_index,
        mode=mode,
        transition_index=state.transition_index + 1,
        feedback_codes=(),
        stop_reason=None,
    )
    return ContinuationReview(
        disposition=ReviewDisposition.ALLOW,
        reason_code="tool_decision_allowed",
        decision_allowed=True,
        state=accepted,
    )


def continuation_prompt_payload(
    state: ContinuationState,
    *,
    blocked_decision: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return non-actionable feedback for the ordinary planner."""

    instruction = (
        "Choose the next uncompleted step for the original task. Do not repeat "
        "an action listed in completed_actions."
        if state.mode == ContinuationMode.REPLAN_REQUIRED
        else "Continue ordinary planning for the original task."
        if state.mode == ContinuationMode.ORDINARY_TASK_PLANNING
        else "Apply the active recovery memory once."
        if state.mode == ContinuationMode.MEMORY_GUIDED
        else "Do not make another tool call; report the stop reason."
    )
    return {
        "continuation": state.to_mapping(),
        "completed_actions": [
            item.to_mapping() for item in state.completed_actions
        ],
        "blocked_decision": (
            dict(blocked_decision) if blocked_decision is not None else None
        ),
        "planning_instruction": instruction,
        "actionable_memory": None,
    }
