"""Observable execution-state continuation layered over the frozen v2.3 ledger.

This module does not select memories or execute tools.  It converts public
post-execution evidence into a bounded continue/verify/revise/stop decision.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping, Sequence

from ..v2_2 import LifecycleStatus, PlanningMode
from .boundary import assert_v2_3_observable_payload
from .contracts import ControllerState, EvidenceSource, ExecutionStatus
from .ledger import ActionExecutionLedger


def _unique(values: Sequence[Any], field_name: str) -> tuple[str, ...]:
    normalized = tuple(str(value) for value in values)
    if any(not value for value in normalized):
        raise ValueError(f"{field_name} cannot contain empty strings")
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{field_name} must contain unique values")
    return normalized


class SubgoalStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class ProgressStatus(str, Enum):
    UNKNOWN = "unknown"
    ADVANCING = "advancing"
    STALLED = "stalled"
    COMPLETE = "complete"
    BLOCKED = "blocked"


class ContinuationDisposition(str, Enum):
    CONTINUE = "continue"
    VERIFY = "verify"
    REVISE = "revise"
    STOP = "stop"


@dataclass(frozen=True)
class SubgoalContract:
    subgoal_id: str
    description: str
    success_evidence_codes: tuple[str, ...]
    status: SubgoalStatus = SubgoalStatus.PENDING

    def __post_init__(self) -> None:
        if not self.subgoal_id or not self.description:
            raise ValueError("subgoal ID and description cannot be empty")
        object.__setattr__(
            self,
            "success_evidence_codes",
            _unique(self.success_evidence_codes, "success_evidence_codes"),
        )
        if not self.success_evidence_codes:
            raise ValueError("subgoal requires observable success evidence")
        if not isinstance(self.status, SubgoalStatus):
            raise ValueError("status must be a SubgoalStatus")

    def to_mapping(self) -> dict[str, Any]:
        return {
            "subgoal_id": self.subgoal_id,
            "description": self.description,
            "success_evidence_codes": list(self.success_evidence_codes),
            "status": self.status.value,
        }


@dataclass(frozen=True)
class ObservableProgressEvidence:
    source: EvidenceSource
    evidence_codes: tuple[str, ...]
    observed_at_step: int
    completed_subgoal_ids: tuple[str, ...] = ()
    task_complete: bool = False
    verified_ledger_entry_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        allowed_sources = {
            EvidenceSource.TOOL_RESULT,
            EvidenceSource.PUBLIC_STATE,
            EvidenceSource.PUBLIC_ENVIRONMENT_CONTRACT,
        }
        if self.source not in allowed_sources:
            raise ValueError("progress requires externally observable evidence")
        object.__setattr__(
            self, "evidence_codes", _unique(self.evidence_codes, "evidence_codes")
        )
        object.__setattr__(
            self,
            "completed_subgoal_ids",
            _unique(self.completed_subgoal_ids, "completed_subgoal_ids"),
        )
        object.__setattr__(
            self,
            "verified_ledger_entry_ids",
            _unique(self.verified_ledger_entry_ids, "verified_ledger_entry_ids"),
        )
        if not self.evidence_codes:
            raise ValueError("progress observation requires evidence codes")
        if self.observed_at_step < 0:
            raise ValueError("observed_at_step cannot be negative")

    def to_mapping(self) -> dict[str, Any]:
        return {
            "source": self.source.value,
            "evidence_codes": list(self.evidence_codes),
            "observed_at_step": self.observed_at_step,
            "completed_subgoal_ids": list(self.completed_subgoal_ids),
            "task_complete": self.task_complete,
            "verified_ledger_entry_ids": list(self.verified_ledger_entry_ids),
        }


@dataclass(frozen=True)
class ExecutionProgressState:
    trajectory_id: str
    subgoals: tuple[SubgoalContract, ...]
    active_subgoal_id: str | None
    progress_status: ProgressStatus = ProgressStatus.UNKNOWN
    consecutive_no_progress: int = 0
    last_verified_evidence: tuple[str, ...] = ()
    uncertain_ledger_entry_ids: tuple[str, ...] = ()
    transition_index: int = 0
    stop_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.trajectory_id:
            raise ValueError("trajectory_id cannot be empty")
        object.__setattr__(self, "subgoals", tuple(self.subgoals))
        ids = [item.subgoal_id for item in self.subgoals]
        if not ids or len(ids) != len(set(ids)):
            raise ValueError("subgoal IDs must be non-empty and unique")
        active = [item.subgoal_id for item in self.subgoals if item.status == SubgoalStatus.ACTIVE]
        if self.active_subgoal_id is None:
            if active:
                raise ValueError("active subgoal status requires active_subgoal_id")
        elif active != [self.active_subgoal_id]:
            raise ValueError("exactly one active subgoal must match active_subgoal_id")
        if self.consecutive_no_progress < 0 or self.transition_index < 0:
            raise ValueError("progress counters cannot be negative")
        object.__setattr__(
            self,
            "last_verified_evidence",
            _unique(self.last_verified_evidence, "last_verified_evidence"),
        )
        object.__setattr__(
            self,
            "uncertain_ledger_entry_ids",
            _unique(self.uncertain_ledger_entry_ids, "uncertain_ledger_entry_ids"),
        )
        terminal = self.progress_status in {ProgressStatus.COMPLETE, ProgressStatus.BLOCKED}
        if terminal != (self.stop_reason is not None):
            raise ValueError("complete or blocked progress state requires a stop reason")
        if not terminal and self.active_subgoal_id is None:
            raise ValueError("non-terminal progress state requires an active subgoal")
        if self.progress_status == ProgressStatus.COMPLETE and any(
            item.status != SubgoalStatus.COMPLETED for item in self.subgoals
        ):
            raise ValueError("complete progress state requires every subgoal completed")

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "method_version": "proper_v2_3_execution_state_continuation_design",
            "trajectory_id": self.trajectory_id,
            "subgoals": [item.to_mapping() for item in self.subgoals],
            "active_subgoal_id": self.active_subgoal_id,
            "progress_status": self.progress_status.value,
            "consecutive_no_progress": self.consecutive_no_progress,
            "last_verified_evidence": list(self.last_verified_evidence),
            "uncertain_ledger_entry_ids": list(self.uncertain_ledger_entry_ids),
            "transition_index": self.transition_index,
            "stop_reason": self.stop_reason,
        }


@dataclass(frozen=True)
class ContinuationDecision:
    disposition: ContinuationDisposition
    reason_code: str
    progress_state: ExecutionProgressState
    controller_state: ControllerState

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "method_version": "proper_v2_3_execution_state_continuation_design",
            "disposition": self.disposition.value,
            "reason_code": self.reason_code,
            "progress_state": self.progress_state.to_mapping(),
            "controller_state": self.controller_state.to_mapping(),
        }


def initial_progress_state(
    *, trajectory_id: str, subgoals: Sequence[SubgoalContract]
) -> ExecutionProgressState:
    normalized = tuple(subgoals)
    if not normalized:
        raise ValueError("at least one subgoal is required")
    if any(item.status != SubgoalStatus.PENDING for item in normalized):
        raise ValueError("initial subgoals must be pending")
    first = normalized[0]
    return ExecutionProgressState(
        trajectory_id=trajectory_id,
        subgoals=(replace(first, status=SubgoalStatus.ACTIVE),) + normalized[1:],
        active_subgoal_id=first.subgoal_id,
    )


def _unresolved_ledger_entries(ledger: ActionExecutionLedger) -> tuple[str, ...]:
    return tuple(
        entry.entry_id
        for entry in ledger.entries
        if entry.decision_allowed
        and entry.status in {ExecutionStatus.EXECUTED, ExecutionStatus.OUTCOME_UNKNOWN}
    )


def _stop_controller(state: ControllerState, reason: str) -> ControllerState:
    return replace(
        state,
        lifecycle_status=LifecycleStatus.STOPPED,
        planning_mode=PlanningMode.STOPPED,
        transition_index=state.transition_index + 1,
        verification_required_for_entry_id=None,
        stop_reason=reason,
    )


def route_observable_progress(
    *,
    progress_state: ExecutionProgressState,
    controller_state: ControllerState,
    ledger: ActionExecutionLedger,
    evidence: ObservableProgressEvidence,
    stall_threshold: int,
) -> ContinuationDecision:
    """Route after one public observation without consulting benchmark gold state."""

    if stall_threshold < 1:
        raise ValueError("stall_threshold must be at least one")
    if progress_state.trajectory_id != ledger.trajectory_id:
        raise ValueError("progress state and ledger trajectory IDs must match")
    if progress_state.stop_reason is not None:
        return ContinuationDecision(
            ContinuationDisposition.STOP,
            progress_state.stop_reason,
            progress_state,
            controller_state,
        )

    unresolved = _unresolved_ledger_entries(ledger)
    verified = set(evidence.verified_ledger_entry_ids)
    entries_by_id = {entry.entry_id: entry for entry in ledger.entries}
    unknown_verified = verified - set(entries_by_id)
    if unknown_verified:
        raise ValueError(f"unknown verified ledger entries: {sorted(unknown_verified)}")
    unclosed_verified = {
        entry_id
        for entry_id in verified
        if entries_by_id[entry_id].status
        in {ExecutionStatus.EXECUTED, ExecutionStatus.OUTCOME_UNKNOWN}
    }
    if unclosed_verified:
        raise ValueError(
            "verification evidence cannot bypass unresolved ledger status: "
            f"{sorted(unclosed_verified)}"
        )
    if unresolved or controller_state.verification_required_for_entry_id is not None:
        updated = replace(
            progress_state,
            progress_status=ProgressStatus.UNKNOWN,
            uncertain_ledger_entry_ids=unresolved,
            transition_index=progress_state.transition_index + 1,
        )
        return ContinuationDecision(
            ContinuationDisposition.VERIFY,
            "unresolved_action_effect_requires_verification",
            updated,
            controller_state,
        )

    requested = set(evidence.completed_subgoal_ids)
    known = {item.subgoal_id for item in progress_state.subgoals}
    if not requested.issubset(known):
        raise ValueError(f"unknown completed subgoals: {sorted(requested - known)}")
    evidence_codes = set(evidence.evidence_codes)
    for item in progress_state.subgoals:
        if item.subgoal_id in requested and not evidence_codes.intersection(
            item.success_evidence_codes
        ):
            raise ValueError(
                f"subgoal {item.subgoal_id} lacks its declared success evidence"
            )

    changed = False
    updated_subgoals: list[SubgoalContract] = []
    for item in progress_state.subgoals:
        if item.subgoal_id in requested and item.status != SubgoalStatus.COMPLETED:
            updated_subgoals.append(replace(item, status=SubgoalStatus.COMPLETED))
            changed = True
        else:
            updated_subgoals.append(item)

    remaining = [item for item in updated_subgoals if item.status != SubgoalStatus.COMPLETED]
    all_complete = not remaining
    if evidence.task_complete and not all_complete:
        raise ValueError("task_complete cannot bypass unfinished subgoals")
    if all_complete:
        completed = replace(
            progress_state,
            subgoals=tuple(updated_subgoals),
            active_subgoal_id=None,
            progress_status=ProgressStatus.COMPLETE,
            consecutive_no_progress=0,
            last_verified_evidence=evidence.evidence_codes,
            uncertain_ledger_entry_ids=(),
            transition_index=progress_state.transition_index + 1,
            stop_reason="observable_task_complete",
        )
        return ContinuationDecision(
            ContinuationDisposition.STOP,
            "observable_task_complete",
            completed,
            _stop_controller(controller_state, "task_complete"),
        )

    if changed:
        next_id = remaining[0].subgoal_id
        activated = tuple(
            replace(item, status=SubgoalStatus.ACTIVE)
            if item.subgoal_id == next_id
            else replace(item, status=SubgoalStatus.PENDING)
            if item.status == SubgoalStatus.ACTIVE
            else item
            for item in updated_subgoals
        )
        advancing = replace(
            progress_state,
            subgoals=activated,
            active_subgoal_id=next_id,
            progress_status=ProgressStatus.ADVANCING,
            consecutive_no_progress=0,
            last_verified_evidence=evidence.evidence_codes,
            uncertain_ledger_entry_ids=(),
            transition_index=progress_state.transition_index + 1,
        )
        return ContinuationDecision(
            ContinuationDisposition.CONTINUE,
            "verified_subgoal_progress_handoff",
            advancing,
            controller_state,
        )

    stalled_count = progress_state.consecutive_no_progress + 1
    stalled = replace(
        progress_state,
        progress_status=ProgressStatus.STALLED,
        consecutive_no_progress=stalled_count,
        last_verified_evidence=evidence.evidence_codes,
        uncertain_ledger_entry_ids=(),
        transition_index=progress_state.transition_index + 1,
    )
    if stalled_count < stall_threshold:
        return ContinuationDecision(
            ContinuationDisposition.CONTINUE,
            "bounded_no_progress_observation",
            stalled,
            controller_state,
        )
    if controller_state.budgets.remaining_replans == 0:
        blocked = replace(
            stalled,
            progress_status=ProgressStatus.BLOCKED,
            active_subgoal_id=None,
            subgoals=tuple(
                replace(item, status=SubgoalStatus.STOPPED)
                if item.status == SubgoalStatus.ACTIVE
                else item
                for item in stalled.subgoals
            ),
            stop_reason="progress_stalled_replan_budget_exhausted",
        )
        return ContinuationDecision(
            ContinuationDisposition.STOP,
            "progress_stalled_replan_budget_exhausted",
            blocked,
            _stop_controller(controller_state, "progress_stalled_replan_budget_exhausted"),
        )
    replanning = replace(
        controller_state,
        budgets=replace(
            controller_state.budgets,
            remaining_replans=controller_state.budgets.remaining_replans - 1,
        ),
        transition_index=controller_state.transition_index + 1,
    )
    revised = replace(
        stalled,
        progress_status=ProgressStatus.UNKNOWN,
        consecutive_no_progress=0,
    )
    return ContinuationDecision(
        ContinuationDisposition.REVISE,
        "progress_stalled_revise_active_subgoal",
        revised,
        replanning,
    )


def progress_state_from_mapping(payload: Mapping[str, Any]) -> ExecutionProgressState:
    """Parse only after recursively rejecting hidden benchmark fields."""

    assert_v2_3_observable_payload(payload)
    subgoals = tuple(
        SubgoalContract(
            subgoal_id=str(item["subgoal_id"]),
            description=str(item["description"]),
            success_evidence_codes=tuple(item["success_evidence_codes"]),
            status=SubgoalStatus(str(item.get("status", "pending"))),
        )
        for item in payload["subgoals"]
    )
    return ExecutionProgressState(
        trajectory_id=str(payload["trajectory_id"]),
        subgoals=subgoals,
        active_subgoal_id=payload.get("active_subgoal_id"),
        progress_status=ProgressStatus(str(payload.get("progress_status", "unknown"))),
        consecutive_no_progress=int(payload.get("consecutive_no_progress", 0)),
        last_verified_evidence=tuple(payload.get("last_verified_evidence", ())),
        uncertain_ledger_entry_ids=tuple(payload.get("uncertain_ledger_entry_ids", ())),
        transition_index=int(payload.get("transition_index", 0)),
        stop_reason=payload.get("stop_reason"),
    )
