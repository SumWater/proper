"""ToolSandbox adapter for the scenario-independent PROPER v2.3 guard."""

from __future__ import annotations

import copy
import json
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT / "src", ROOT / "experiments" / "proper_v2"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import lifecycle_development_v2_2 as lifecycle  # noqa: E402
import toolsandbox_model_pilot_runner_validation_v2_1 as engine  # noqa: E402
from failure_memory.proper_v2 import DecisionPhase, RecoveryOperation, RetrySafety  # noqa: E402
from failure_memory.proper_v2.v2_2 import (  # noqa: E402
    EvidenceStatus, LifecycleStatus, PlanningMode, TriggerStatus,
)
from failure_memory.proper_v2.v2_3 import (  # noqa: E402
    ActionEffectClass, ActionEffectContract, ActionExecutionLedger,
    ActionPurpose, ActionSpec, BudgetPolicy, ControllerDisposition,
    EvidenceRecord, EvidenceSource, ExecutionStatus,
    initial_controller_state, observe_execution, review_action_proposal,
    resolve_verification, review_invalid_decision, stop_for_agent_decision,
)

FIFTH_CONDITION = "proper_v2_3_full_ledger_controller"


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class PublicEffectRegistry:
    def __init__(self, payload: Mapping[str, Any]) -> None:
        self.records = {str(item["action_name"]): dict(item) for item in payload["contracts"]}
        if len(self.records) != int(payload["source"]["unique_available_tool_count"]):
            raise ValueError("public effect registry contains duplicate or missing tools")

    def record(self, action_name: str) -> Mapping[str, Any] | None:
        return self.records.get(action_name)

    def contract(self, action_name: str) -> ActionEffectContract:
        item = self.record(action_name)
        if item is None:
            return ActionEffectContract(
                effect_class=ActionEffectClass.UNKNOWN_EFFECT,
                classification_evidence=("public_contract:unregistered_action",),
                retry_safety=RetrySafety.UNKNOWN,
            )
        verification = item.get("verification_action")
        return ActionEffectContract(
            effect_class=ActionEffectClass(str(item["effect_class"])),
            classification_evidence=tuple(item["effect_evidence"]),
            retry_safety=RetrySafety(str(item["retry_safety"])),
            retry_safety_evidence=tuple(item["retry_safety_evidence"]),
            verification_supported=verification is not None,
            verification_evidence=(
                ("public_contract:declared_read_only_verification",)
                if verification is not None else ()
            ),
        )

    def verification_action(self, action_name: str) -> ActionSpec | None:
        item = self.record(action_name)
        verification = item.get("verification_action") if item else None
        if verification is None:
            return None
        if verification["argument_policy"] != "empty_arguments":
            raise ValueError("unsupported public verification argument policy")
        return ActionSpec(str(verification["action_name"]), {})

    def verification_evidence_status(
        self,
        *,
        original_action: ActionSpec,
        verification_result: Any,
    ) -> EvidenceStatus:
        item = self.record(original_action.tool_name)
        verification = item.get("verification_action") if item else None
        if verification is None:
            return EvidenceStatus.UNKNOWN
        if verification.get("expected_evidence") != "returned_state_equals_requested_on":
            return EvidenceStatus.UNKNOWN
        requested = original_action.arguments.get("on")
        if not isinstance(requested, bool) or not isinstance(verification_result, bool):
            return EvidenceStatus.UNKNOWN
        return (
            EvidenceStatus.SATISFIED
            if verification_result is requested
            else EvidenceStatus.VIOLATED
        )


@dataclass
class GuardRuntime:
    state: Any
    ledger: ActionExecutionLedger
    synchronized_history_count: int
    pending_entry_ids: list[str]
    blocked_attempts: list[dict[str, Any]]
    prefix_entry_count: int


class ExecutionAwareTrajectoryGuard:
    """Bridge visible ToolSandbox history to the generic v2.3 controller."""

    def __init__(
        self,
        *,
        record: Mapping[str, Any],
        config: Mapping[str, Any],
        effect_registry: PublicEffectRegistry,
        prefix_history: list[dict[str, Any]],
    ) -> None:
        self.record = record
        self.effect_registry = effect_registry
        self.phase = DecisionPhase(str(record["decision_phase"]))
        condition = record["conditions"][FIFTH_CONDITION]
        memory = condition["memory"]
        proposed = memory.get("proposed_action")
        memory_action = (
            ActionSpec(str(proposed["tool_name"]), proposed["argument_template"])
            if proposed is not None else None
        )
        budget = config["controller_budget"]
        policy = BudgetPolicy(
            maximum_retries=int(budget["maximum_retries"]),
            maximum_verifications=int(budget["maximum_verifications"]),
            maximum_invalid_decisions=int(budget["maximum_invalid_decisions"]),
            maximum_replans=int(budget["maximum_replans"]),
        )
        state = initial_controller_state(
            phase=self.phase,
            selected_memory_experience_id=str(memory["experience_id"]),
            memory_operation=RecoveryOperation(str(memory["recovery_operation"])),
            memory_action=memory_action,
            budget_policy=policy,
        )
        ledger = ActionExecutionLedger(
            trajectory_id=f"{record['pair_id']}:{FIFTH_CONDITION}"
        )
        self.runtime = GuardRuntime(
            state=state, ledger=ledger, synchronized_history_count=0,
            pending_entry_ids=[], blocked_attempts=[], prefix_entry_count=0,
        )
        for item in prefix_history:
            self._record_prefix_item(item)
        self.runtime.prefix_entry_count = len(self.runtime.ledger.entries)

    def _outcome_evidence(self, item: Mapping[str, Any], step: int) -> tuple[ExecutionStatus, EvidenceRecord]:
        if item.get("outcome_unknown") is True:
            return ExecutionStatus.OUTCOME_UNKNOWN, EvidenceRecord(
                EvidenceSource.PUBLIC_ENVIRONMENT_CONTRACT,
                "visible_runtime:outcome_unknown", step,
            )
        if item.get("exception") is not None:
            return ExecutionStatus.FAILED, EvidenceRecord(
                EvidenceSource.TOOL_RESULT, "visible_tool_exception:failed", step,
            )
        return ExecutionStatus.SUCCEEDED, EvidenceRecord(
            EvidenceSource.TOOL_RESULT, "visible_tool_result:succeeded", step,
        )

    def _record_prefix_item(self, item: Mapping[str, Any]) -> None:
        action = ActionSpec(str(item["tool_name"]), item["arguments"])
        contract = self.effect_registry.contract(action.tool_name)
        ledger, entry = self.runtime.ledger.append_proposal(
            action=action, effect_contract=contract, phase=self.phase,
            purpose=ActionPurpose.ORDINARY_TASK,
            disposition=ControllerDisposition.ALLOW, decision_allowed=True,
            reason_codes=("observed_prefix_action_before_controller_start",),
        )
        ledger = ledger.mark_executed(entry.entry_id)
        status, evidence = self._outcome_evidence(item, entry.sequence_index)
        self.runtime.ledger = ledger.record_outcome(
            entry.entry_id, status=status, evidence=(evidence,)
        )

    def _align_lifecycle(self, lifecycle_state: Any) -> None:
        if self.runtime.state.lifecycle_status in {LifecycleStatus.FAILED, LifecycleStatus.STOPPED}:
            return
        if (
            self.runtime.state.lifecycle_status == LifecycleStatus.ACTIVE
            and lifecycle_state.status == LifecycleStatus.CONSUMED
        ):
            # The v2.3 execution observation is authoritative for consumption.
            # The legacy lifecycle cannot represent outcome_unknown or resolve
            # declared verification evidence and therefore cannot promote it.
            return
        self.runtime.state = replace(
            self.runtime.state,
            lifecycle_status=lifecycle_state.status,
            planning_mode=lifecycle_state.planning_mode,
            stop_reason=(
                str(lifecycle_state.stop_reason or "terminal_lifecycle")
                if lifecycle_state.status in {LifecycleStatus.FAILED, LifecycleStatus.STOPPED}
                else None
            ),
        )

    def sync_history(self, history: list[dict[str, Any]], lifecycle_state: Any) -> None:
        while self.runtime.synchronized_history_count < len(history):
            if not self.runtime.pending_entry_ids:
                raise RuntimeError("executed tool history has no allowed ledger proposal")
            item = history[self.runtime.synchronized_history_count]
            entry_id = self.runtime.pending_entry_ids.pop(0)
            entry = self.runtime.ledger.entry(entry_id)
            observed = ActionSpec(str(item["tool_name"]), item["arguments"])
            if observed.identity != entry.normalized_identity:
                raise RuntimeError("executed tool does not match allowed ledger proposal")
            ledger = self.runtime.ledger.mark_executed(entry_id)
            status, evidence = self._outcome_evidence(item, entry.sequence_index)
            ledger = ledger.record_outcome(entry_id, status=status, evidence=(evidence,))
            self.runtime.ledger = ledger
            trigger = TriggerStatus.UNKNOWN
            success = EvidenceStatus.UNKNOWN
            if entry.purpose == ActionPurpose.VERIFICATION:
                if not entry.related_entry_ids:
                    raise RuntimeError("verification ledger entry lacks its target")
                verified_entry_id = entry.related_entry_ids[0]
                verified_entry = self.runtime.ledger.entry(verified_entry_id)
                verification_status = self.effect_registry.verification_evidence_status(
                    original_action=verified_entry.action,
                    verification_result=item.get("result"),
                )
                if status == ExecutionStatus.SUCCEEDED and verification_status in {
                    EvidenceStatus.SATISFIED,
                    EvidenceStatus.VIOLATED,
                }:
                    resolved_status = (
                        ExecutionStatus.SUCCEEDED
                        if verification_status == EvidenceStatus.SATISFIED
                        else ExecutionStatus.FAILED
                    )
                    resolution_evidence = EvidenceRecord(
                        EvidenceSource.PUBLIC_STATE,
                        "declared_read_only_verification:"
                        + verification_status.value,
                        entry.sequence_index,
                    )
                    self.runtime.ledger = self.runtime.ledger.record_outcome(
                        verified_entry_id,
                        status=resolved_status,
                        evidence=(resolution_evidence,),
                    )
                    self.runtime.state = resolve_verification(
                        state=self.runtime.state,
                        ledger=self.runtime.ledger,
                        verified_entry_id=verified_entry_id,
                        verified_status=resolved_status,
                        trigger_status=(
                            TriggerStatus.CLEARED
                            if verification_status == EvidenceStatus.SATISFIED
                            else TriggerStatus.HOLDS
                        ),
                        success_evidence_status=verification_status,
                    )
                else:
                    self.runtime.state = stop_for_agent_decision(
                        self.runtime.state,
                        reason_code="verification_execution_failed_or_inconclusive",
                    )
                self.runtime.synchronized_history_count += 1
                continue
            if (
                entry.normalized_identity == self.runtime.state.memory_action_identity
                and status == ExecutionStatus.SUCCEEDED
                and lifecycle_state.status == LifecycleStatus.CONSUMED
            ):
                trigger = TriggerStatus.CLEARED
                success = EvidenceStatus.SATISFIED
            self.runtime.state = observe_execution(
                state=self.runtime.state, ledger=ledger, entry_id=entry_id,
                trigger_status=trigger, success_evidence_status=success,
            )
            self.runtime.synchronized_history_count += 1
        self._align_lifecycle(lifecycle_state)

    def _purpose(self, action: ActionSpec) -> ActionPurpose:
        if (
            self.runtime.state.lifecycle_status == LifecycleStatus.ACTIVE
            and action.identity == self.runtime.state.memory_action_identity
        ):
            return ActionPurpose.RECOVERY
        return ActionPurpose.ORDINARY_TASK

    def review(self, proposed: Mapping[str, Any], *, valid: bool) -> dict[str, Any]:
        if not valid or proposed.get("kind") not in {"tool", "stop"}:
            decision = review_invalid_decision(self.runtime.state)
            self.runtime.state = decision.state
            return {"decision": decision, "action": None, "verification": False}
        if proposed["kind"] == "stop":
            self.runtime.state = stop_for_agent_decision(
                self.runtime.state, reason_code=str(proposed.get("reason_code", "agent_stop"))
            )
            return {"decision": None, "action": None, "verification": False}
        action = ActionSpec(str(proposed["tool_name"]), proposed["arguments"])
        purpose = self._purpose(action)
        verifies_entry_id = None
        required = self.runtime.state.verification_required_for_entry_id
        if required is not None:
            original = self.runtime.ledger.entry(required)
            verification = self.effect_registry.verification_action(original.action.tool_name)
            if verification is not None and verification.identity == action.identity:
                purpose = ActionPurpose.VERIFICATION
                verifies_entry_id = required
        ledger, decision = review_action_proposal(
            state=self.runtime.state, ledger=self.runtime.ledger, action=action,
            effect_contract=self.effect_registry.contract(action.tool_name),
            purpose=purpose, verifies_entry_id=verifies_entry_id,
        )
        self.runtime.ledger = ledger
        self.runtime.state = decision.state
        if decision.decision_allowed:
            self.runtime.pending_entry_ids.append(str(decision.ledger_entry_id))
        return {"decision": decision, "action": action, "verification": False}

    def feedback_payload(self, *, review: Mapping[str, Any], proposed: Mapping[str, Any]) -> dict[str, Any]:
        decision = review["decision"]
        verification_action = None
        if decision is not None and decision.disposition == ControllerDisposition.VERIFY:
            required = self.runtime.state.verification_required_for_entry_id
            if required is not None:
                original = self.runtime.ledger.entry(required)
                candidate = self.effect_registry.verification_action(original.action.tool_name)
                verification_action = candidate.to_mapping() if candidate else None
        return {
            "controller_disposition": decision.disposition.value if decision else "stop",
            "reason_code": decision.reason_code if decision else self.runtime.state.stop_reason,
            "blocked_action": dict(proposed),
            "verification_action": verification_action,
            "observable_evidence": [],
            "remaining_controller_budgets": self.runtime.state.budgets.to_mapping(),
            "action_execution_ledger": self.runtime.ledger.to_mapping(),
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            "state": self.runtime.state.to_mapping(),
            "ledger": self.runtime.ledger.to_mapping(),
            "prefix_entry_count": self.runtime.prefix_entry_count,
            "synchronized_history_count": self.runtime.synchronized_history_count,
            "pending_allowed_execution_count": len(self.runtime.pending_entry_ids),
            "blocked_attempts": copy.deepcopy(self.runtime.blocked_attempts),
        }

    def finalize_summary(
        self,
        *,
        history: list[dict[str, Any]],
        lifecycle_state: Any,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Synchronize the last accepted action and produce safety accounting."""
        self.sync_history(history, lifecycle_state)
        snapshot = self.snapshot()
        entries = snapshot["ledger"]["entries"]
        allowed_unresolved = [
            item
            for item in entries
            if item["decision_allowed"]
            and item["status"] in {
                ExecutionStatus.PROPOSED.value,
                ExecutionStatus.EXECUTED.value,
            }
        ]
        non_idempotent_successes: dict[str, int] = {}
        for item in entries:
            if (
                item["effect_contract"]["effect_class"]
                == ActionEffectClass.NON_IDEMPOTENT_SIDE_EFFECT.value
                and item["status"] == ExecutionStatus.SUCCEEDED.value
            ):
                identity = str(item["action"]["normalized_identity"])
                non_idempotent_successes[identity] = (
                    non_idempotent_successes.get(identity, 0) + 1
                )
        safety = {
            "allowed_unresolved_entry_count": len(allowed_unresolved),
            "blocked_proposal_count": sum(
                not item["decision_allowed"] for item in entries
            ),
            "duplicate_non_idempotent_execution_count": sum(
                max(0, count - 1)
                for count in non_idempotent_successes.values()
            ),
            "complete_trajectory_ledger_entry_count": len(entries),
            "prefix_entry_count": snapshot["prefix_entry_count"],
            "executed_tool_history_count": len(history),
            "all_allowed_executions_resolved": not allowed_unresolved,
        }
        return snapshot, safety
