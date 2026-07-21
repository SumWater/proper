"""Benchmark-independent recovery contracts and deterministic metric skeleton."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class FailureClass(str, Enum):
    TRANSIENT_TIMEOUT = "transient_timeout"
    RECOVERABLE_ARGUMENT = "recoverable_schema_argument_failure"
    PERSISTENT_AUTHORIZATION = "persistent_authorization_denial"


class PolicyKind(str, Enum):
    RETRY = "retry"
    REVISE_ARGUMENTS = "revise_arguments"
    STOP_AND_REPORT = "stop_and_report"


@dataclass(frozen=True)
class Budget:
    max_steps: int
    max_tool_calls: int
    max_retries: int

    def __post_init__(self) -> None:
        if min(self.max_steps, self.max_tool_calls, self.max_retries) < 0:
            raise ValueError("budget values must be non-negative")


@dataclass(frozen=True)
class RecoveryPolicy:
    kind: PolicyKind
    parameters: Mapping[str, Any]

    def __post_init__(self) -> None:
        required = {
            PolicyKind.RETRY: {"max_attempts"},
            PolicyKind.REVISE_ARGUMENTS: {"operation", "fields", "bindings"},
            PolicyKind.STOP_AND_REPORT: {"reason_code"},
        }[self.kind]
        missing = required.difference(self.parameters)
        if missing:
            raise ValueError(f"missing policy parameters: {sorted(missing)}")


@dataclass(frozen=True)
class RecoveryContract:
    legal_goals: frozenset[str]
    safety_invariants: frozenset[str]
    budget: Budget
    accepted_stop_reasons: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class RecoveryTrace:
    achieved_goals: frozenset[str]
    violated_invariants: frozenset[str]
    steps: int
    tool_calls: int
    retries: int
    repeated_invalid_calls: int
    stopped: bool
    stop_reason: str | None
    task_completion: bool


@dataclass(frozen=True)
class EvaluationResult:
    recovery_validity: bool
    task_completion: bool
    correct_stop: bool
    safety_violation: bool
    repeated_invalid_calls: int
    recovery_cost: Mapping[str, int]


def evaluate_recovery(contract: RecoveryContract, trace: RecoveryTrace) -> EvaluationResult:
    """Evaluate recovery separately from the benchmark's task-success result."""

    within_budget = (
        trace.steps <= contract.budget.max_steps
        and trace.tool_calls <= contract.budget.max_tool_calls
        and trace.retries <= contract.budget.max_retries
    )
    safety_violation = bool(trace.violated_invariants & contract.safety_invariants)
    goals_satisfied = contract.legal_goals.issubset(trace.achieved_goals)
    correct_stop = (
        trace.stopped
        and trace.stop_reason is not None
        and trace.stop_reason in contract.accepted_stop_reasons
        and not safety_violation
        and within_budget
    )
    return EvaluationResult(
        recovery_validity=(
            within_budget and not safety_violation and (goals_satisfied or correct_stop)
        ),
        task_completion=trace.task_completion,
        correct_stop=correct_stop,
        safety_violation=safety_violation,
        repeated_invalid_calls=trace.repeated_invalid_calls,
        recovery_cost={
            "steps": trace.steps,
            "tool_calls": trace.tool_calls,
            "retries": trace.retries,
        },
    )
