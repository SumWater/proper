"""CPU-only traces for observable execution-state continuation."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from failure_memory.proper_v2 import DecisionPhase, RecoveryOperation, RetrySafety  # noqa: E402
from failure_memory.proper_v2.v2_2 import EvidenceStatus, TriggerStatus  # noqa: E402
from failure_memory.proper_v2.v2_3 import (  # noqa: E402
    ActionEffectClass,
    ActionEffectContract,
    ActionExecutionLedger,
    ActionPurpose,
    ActionSpec,
    BudgetPolicy,
    ContinuationDisposition,
    EvidenceRecord,
    EvidenceSource,
    ExecutionStatus,
    ObservableProgressEvidence,
    SubgoalContract,
    initial_controller_state,
    initial_progress_state,
    observe_execution,
    review_action_proposal,
    route_observable_progress,
)


def _contract(effect: ActionEffectClass) -> ActionEffectContract:
    retry = (
        RetrySafety.UNSAFE
        if effect == ActionEffectClass.NON_IDEMPOTENT_SIDE_EFFECT
        else RetrySafety.SAFE
    )
    return ActionEffectContract(
        effect_class=effect,
        classification_evidence=(f"tool_schema:{effect.value}",),
        retry_safety=retry,
        retry_safety_evidence=("public_contract:declared_retry_behavior",),
        verification_supported=True,
        verification_evidence=("tool_schema:public_state_query",),
    )


def _execute(
    ledger: ActionExecutionLedger,
    entry_id: str,
    status: ExecutionStatus,
    code: str,
    step: int,
) -> ActionExecutionLedger:
    ledger = ledger.mark_executed(
        entry_id,
        evidence=(EvidenceRecord(EvidenceSource.CONTROLLER, "allowed", step),),
    )
    return ledger.record_outcome(
        entry_id,
        status=status,
        evidence=(EvidenceRecord(EvidenceSource.TOOL_RESULT, code, step),),
    )


def _consumed_start(trajectory_id: str) -> tuple[Any, ActionExecutionLedger]:
    recovery = ActionSpec("restore_public_prerequisite", {"enabled": True})
    controller = initial_controller_state(
        phase=DecisionPhase.POST_FAILURE,
        selected_memory_experience_id="development-memory::observable-recovery",
        memory_operation=RecoveryOperation.INVOKE_PREREQUISITE,
        memory_action=recovery,
        budget_policy=BudgetPolicy(maximum_replans=2),
    )
    ledger, decision = review_action_proposal(
        state=controller,
        ledger=ActionExecutionLedger(trajectory_id),
        action=recovery,
        effect_contract=_contract(ActionEffectClass.IDEMPOTENT_STATE_SETTING),
        purpose=ActionPurpose.RECOVERY,
    )
    if decision.ledger_entry_id is None:
        raise AssertionError("recovery proposal lacks ledger entry")
    ledger = _execute(
        ledger,
        decision.ledger_entry_id,
        ExecutionStatus.SUCCEEDED,
        "public_state:prerequisite_restored",
        1,
    )
    controller = observe_execution(
        state=decision.state,
        ledger=ledger,
        entry_id=decision.ledger_entry_id,
        trigger_status=TriggerStatus.CLEARED,
        success_evidence_status=EvidenceStatus.SATISFIED,
    )
    return controller, ledger


def _progress(trajectory_id: str) -> Any:
    return initial_progress_state(
        trajectory_id=trajectory_id,
        subgoals=(
            SubgoalContract(
                "inspect",
                "Inspect the public state needed for the remaining task.",
                ("public_state:record_available",),
            ),
            SubgoalContract(
                "apply",
                "Apply the remaining task change exactly once.",
                ("tool_result:change_applied",),
            ),
        ),
    )


def trace_recovery_handoff_and_completion() -> dict[str, Any]:
    trajectory_id = "continuation-handoff-completion"
    controller, ledger = _consumed_start(trajectory_id)
    progress = _progress(trajectory_id)
    first = route_observable_progress(
        progress_state=progress,
        controller_state=controller,
        ledger=ledger,
        evidence=ObservableProgressEvidence(
            EvidenceSource.PUBLIC_STATE,
            ("public_state:record_available",),
            2,
            completed_subgoal_ids=("inspect",),
        ),
        stall_threshold=2,
    )
    second = route_observable_progress(
        progress_state=first.progress_state,
        controller_state=first.controller_state,
        ledger=ledger,
        evidence=ObservableProgressEvidence(
            EvidenceSource.TOOL_RESULT,
            ("tool_result:change_applied",),
            3,
            completed_subgoal_ids=("apply",),
            task_complete=True,
        ),
        stall_threshold=2,
    )
    return {
        "trace_id": trajectory_id,
        "passed": (
            first.disposition == ContinuationDisposition.CONTINUE
            and first.progress_state.active_subgoal_id == "apply"
            and second.disposition == ContinuationDisposition.STOP
            and second.reason_code == "observable_task_complete"
        ),
        "first": first.to_mapping(),
        "second": second.to_mapping(),
    }


def trace_progress_stall_routes_to_bounded_revision() -> dict[str, Any]:
    trajectory_id = "continuation-progress-stall"
    controller, ledger = _consumed_start(trajectory_id)
    progress = _progress(trajectory_id)
    evidence = ObservableProgressEvidence(
        EvidenceSource.PUBLIC_STATE,
        ("public_state:no_declared_change",),
        2,
    )
    first = route_observable_progress(
        progress_state=progress,
        controller_state=controller,
        ledger=ledger,
        evidence=evidence,
        stall_threshold=2,
    )
    second = route_observable_progress(
        progress_state=first.progress_state,
        controller_state=first.controller_state,
        ledger=ledger,
        evidence=ObservableProgressEvidence(
            EvidenceSource.PUBLIC_STATE,
            ("public_state:still_no_declared_change",),
            3,
        ),
        stall_threshold=2,
    )
    after_revision = route_observable_progress(
        progress_state=second.progress_state,
        controller_state=second.controller_state,
        ledger=ledger,
        evidence=ObservableProgressEvidence(
            EvidenceSource.PUBLIC_STATE,
            ("public_state:revision_cooldown_observation",),
            4,
        ),
        stall_threshold=2,
    )
    return {
        "trace_id": trajectory_id,
        "passed": (
            first.disposition == ContinuationDisposition.CONTINUE
            and second.disposition == ContinuationDisposition.REVISE
            and second.controller_state.budgets.remaining_replans == 1
            and after_revision.disposition == ContinuationDisposition.CONTINUE
            and after_revision.controller_state.budgets.remaining_replans == 1
        ),
        "first": first.to_mapping(),
        "second": second.to_mapping(),
        "after_revision": after_revision.to_mapping(),
    }


def trace_unknown_effect_precedes_continuation() -> dict[str, Any]:
    trajectory_id = "continuation-unknown-effect"
    controller, ledger = _consumed_start(trajectory_id)
    action = ActionSpec("apply_external_change", {"value": "once"})
    ledger, proposal = review_action_proposal(
        state=controller,
        ledger=ledger,
        action=action,
        effect_contract=_contract(ActionEffectClass.NON_IDEMPOTENT_SIDE_EFFECT),
        purpose=ActionPurpose.ORDINARY_TASK,
    )
    if proposal.ledger_entry_id is None:
        raise AssertionError("ordinary proposal lacks ledger entry")
    ledger = _execute(
        ledger,
        proposal.ledger_entry_id,
        ExecutionStatus.OUTCOME_UNKNOWN,
        "transport:response_lost",
        2,
    )
    controller = observe_execution(
        state=proposal.state,
        ledger=ledger,
        entry_id=proposal.ledger_entry_id,
    )
    decision = route_observable_progress(
        progress_state=_progress(trajectory_id),
        controller_state=controller,
        ledger=ledger,
        evidence=ObservableProgressEvidence(
            EvidenceSource.PUBLIC_STATE,
            ("public_state:effect_not_yet_verified",),
            3,
        ),
        stall_threshold=2,
    )
    return {
        "trace_id": trajectory_id,
        "passed": (
            decision.disposition == ContinuationDisposition.VERIFY
            and proposal.ledger_entry_id
            in decision.progress_state.uncertain_ledger_entry_ids
        ),
        "decision": decision.to_mapping(),
    }


def trace_hidden_or_self_reported_completion_rejected() -> dict[str, Any]:
    trajectory_id = "continuation-evidence-boundary"
    controller, ledger = _consumed_start(trajectory_id)
    self_report_rejected = False
    incomplete_task_rejected = False
    try:
        ObservableProgressEvidence(
            EvidenceSource.AGENT_DECISION,
            ("agent_claim:complete",),
            2,
            completed_subgoal_ids=("inspect", "apply"),
            task_complete=True,
        )
    except ValueError:
        self_report_rejected = True
    try:
        route_observable_progress(
            progress_state=_progress(trajectory_id),
            controller_state=controller,
            ledger=ledger,
            evidence=ObservableProgressEvidence(
                EvidenceSource.PUBLIC_STATE,
                ("public_state:record_available",),
                2,
                completed_subgoal_ids=("inspect",),
                task_complete=True,
            ),
            stall_threshold=2,
        )
    except ValueError:
        incomplete_task_rejected = True
    return {
        "trace_id": trajectory_id,
        "passed": self_report_rejected and incomplete_task_rejected,
        "self_report_rejected": self_report_rejected,
        "incomplete_task_rejected": incomplete_task_rejected,
    }


def run_scripted_continuation_traces() -> dict[str, Any]:
    traces = [
        trace_recovery_handoff_and_completion(),
        trace_progress_stall_routes_to_bounded_revision(),
        trace_unknown_effect_precedes_continuation(),
        trace_hidden_or_self_reported_completion_rejected(),
    ]
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_3_execution_state_continuation_scripted_validation",
        "model_loaded": False,
        "model_outputs_read": False,
        "gpu_used": False,
        "scenario_specific_controller_branch_count": 0,
        "trace_count": len(traces),
        "passed_trace_count": sum(bool(item["passed"]) for item in traces),
        "passed": all(bool(item["passed"]) for item in traces),
        "traces": traces,
    }


def main() -> int:
    result = run_scripted_continuation_traces()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
