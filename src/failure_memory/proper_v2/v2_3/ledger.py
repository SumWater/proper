"""Append-only complete-trajectory action ledger for PROPER v2.3."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from typing import Any, Sequence

from ..contracts import DecisionPhase
from .contracts import (
    ActionEffectContract,
    ActionPurpose,
    ActionSpec,
    ControllerDisposition,
    EvidenceRecord,
    ExecutionStatus,
    _unique,
)


@dataclass(frozen=True)
class LedgerEntry:
    entry_id: str
    sequence_index: int
    action: ActionSpec
    effect_contract: ActionEffectContract
    phase: DecisionPhase
    purpose: ActionPurpose
    status: ExecutionStatus
    controller_disposition: ControllerDisposition
    decision_allowed: bool
    reason_codes: tuple[str, ...]
    related_entry_ids: tuple[str, ...] = ()
    evidence: tuple[EvidenceRecord, ...] = ()

    def __post_init__(self) -> None:
        if not self.entry_id:
            raise ValueError("ledger entry_id cannot be empty")
        if self.sequence_index < 0:
            raise ValueError("ledger sequence_index cannot be negative")
        if not isinstance(self.phase, DecisionPhase):
            raise ValueError("ledger phase must be a DecisionPhase")
        if not isinstance(self.purpose, ActionPurpose):
            raise ValueError("ledger purpose must be an ActionPurpose")
        if not isinstance(self.status, ExecutionStatus):
            raise ValueError("ledger status must be an ExecutionStatus")
        if not isinstance(self.controller_disposition, ControllerDisposition):
            raise ValueError(
                "controller_disposition must be a ControllerDisposition"
            )
        object.__setattr__(self, "reason_codes", _unique(self.reason_codes, "reason_codes"))
        object.__setattr__(
            self,
            "related_entry_ids",
            _unique(self.related_entry_ids, "related_entry_ids"),
        )
        object.__setattr__(self, "evidence", tuple(self.evidence))
        if any(not isinstance(item, EvidenceRecord) for item in self.evidence):
            raise ValueError("ledger evidence must contain EvidenceRecord values")
        if not self.reason_codes:
            raise ValueError("ledger entry requires a reason code")
        if self.decision_allowed and self.controller_disposition in {
            ControllerDisposition.REPLAN,
            ControllerDisposition.STOP,
        }:
            raise ValueError("blocked disposition cannot allow execution")
        if not self.decision_allowed and self.status != ExecutionStatus.PROPOSED:
            raise ValueError("blocked ledger entry must remain proposed")

    @property
    def normalized_identity(self) -> str:
        return self.action.identity

    def to_mapping(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "sequence_index": self.sequence_index,
            "action": self.action.to_mapping(),
            "effect_contract": self.effect_contract.to_mapping(),
            "phase": self.phase.value,
            "purpose": self.purpose.value,
            "status": self.status.value,
            "controller_disposition": self.controller_disposition.value,
            "decision_allowed": self.decision_allowed,
            "reason_codes": list(self.reason_codes),
            "related_entry_ids": list(self.related_entry_ids),
            "evidence": [item.to_mapping() for item in self.evidence],
        }


@dataclass(frozen=True)
class ActionExecutionLedger:
    trajectory_id: str
    entries: tuple[LedgerEntry, ...] = ()

    def __post_init__(self) -> None:
        if not self.trajectory_id:
            raise ValueError("trajectory_id cannot be empty")
        object.__setattr__(self, "entries", tuple(self.entries))
        if any(not isinstance(entry, LedgerEntry) for entry in self.entries):
            raise ValueError("ledger entries must contain LedgerEntry values")
        ids = [entry.entry_id for entry in self.entries]
        if len(ids) != len(set(ids)):
            raise ValueError("ledger entry IDs must be unique")
        expected = list(range(len(self.entries)))
        actual = [entry.sequence_index for entry in self.entries]
        if actual != expected:
            raise ValueError("ledger sequence indices must be contiguous")
        prior_ids: set[str] = set()
        for entry in self.entries:
            unknown = set(entry.related_entry_ids) - prior_ids
            if unknown:
                raise ValueError(
                    "related ledger entries must refer to earlier entries: "
                    f"{sorted(unknown)}"
                )
            prior_ids.add(entry.entry_id)

    def matching_entries(
        self,
        action_identity: str,
        *,
        statuses: Sequence[ExecutionStatus] | None = None,
    ) -> tuple[LedgerEntry, ...]:
        accepted = set(statuses) if statuses is not None else None
        return tuple(
            entry
            for entry in self.entries
            if entry.normalized_identity == action_identity
            and (accepted is None or entry.status in accepted)
        )

    def entry(self, entry_id: str) -> LedgerEntry:
        try:
            return next(item for item in self.entries if item.entry_id == entry_id)
        except StopIteration as exc:
            raise ValueError(f"unknown ledger entry_id: {entry_id}") from exc

    def append_proposal(
        self,
        *,
        action: ActionSpec,
        effect_contract: ActionEffectContract,
        phase: DecisionPhase,
        purpose: ActionPurpose,
        disposition: ControllerDisposition,
        decision_allowed: bool,
        reason_codes: Sequence[str],
        related_entry_ids: Sequence[str] = (),
    ) -> tuple["ActionExecutionLedger", LedgerEntry]:
        sequence = len(self.entries)
        seed = f"{self.trajectory_id}|{sequence}|{action.identity}"
        entry_id = hashlib.sha256(seed.encode("utf-8")).hexdigest()
        entry = LedgerEntry(
            entry_id=entry_id,
            sequence_index=sequence,
            action=action,
            effect_contract=effect_contract,
            phase=phase,
            purpose=purpose,
            status=ExecutionStatus.PROPOSED,
            controller_disposition=disposition,
            decision_allowed=decision_allowed,
            reason_codes=tuple(reason_codes),
            related_entry_ids=tuple(related_entry_ids),
        )
        return replace(self, entries=self.entries + (entry,)), entry

    def mark_executed(
        self,
        entry_id: str,
        *,
        evidence: Sequence[EvidenceRecord] = (),
    ) -> "ActionExecutionLedger":
        return self._transition(
            entry_id,
            expected=(ExecutionStatus.PROPOSED,),
            status=ExecutionStatus.EXECUTED,
            evidence=evidence,
        )

    def record_outcome(
        self,
        entry_id: str,
        *,
        status: ExecutionStatus,
        evidence: Sequence[EvidenceRecord],
    ) -> "ActionExecutionLedger":
        evidence = tuple(evidence)
        if not evidence:
            raise ValueError("execution outcome requires observable evidence")
        if status not in {
            ExecutionStatus.SUCCEEDED,
            ExecutionStatus.FAILED,
            ExecutionStatus.OUTCOME_UNKNOWN,
        }:
            raise ValueError("record_outcome requires a terminal or unknown outcome")
        current = self.entry(entry_id)
        expected = (
            (ExecutionStatus.EXECUTED,)
            if current.status == ExecutionStatus.EXECUTED
            else (ExecutionStatus.OUTCOME_UNKNOWN,)
        )
        if (
            current.status == ExecutionStatus.OUTCOME_UNKNOWN
            and status == ExecutionStatus.OUTCOME_UNKNOWN
        ):
            raise ValueError("unknown outcome cannot transition to itself")
        return self._transition(
            entry_id,
            expected=expected,
            status=status,
            evidence=evidence,
        )

    def _transition(
        self,
        entry_id: str,
        *,
        expected: Sequence[ExecutionStatus],
        status: ExecutionStatus,
        evidence: Sequence[EvidenceRecord],
    ) -> "ActionExecutionLedger":
        updated: list[LedgerEntry] = []
        found = False
        for item in self.entries:
            if item.entry_id != entry_id:
                updated.append(item)
                continue
            found = True
            if not item.decision_allowed:
                raise ValueError("blocked proposal cannot be executed")
            if item.status not in set(expected):
                raise ValueError(
                    f"invalid ledger transition {item.status.value} -> {status.value}"
                )
            updated.append(
                replace(
                    item,
                    status=status,
                    evidence=item.evidence + tuple(evidence),
                )
            )
        if not found:
            raise ValueError(f"unknown ledger entry_id: {entry_id}")
        return replace(self, entries=tuple(updated))

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "method_version": "proper_v2_3_action_execution_ledger_development",
            "trajectory_id": self.trajectory_id,
            "entries": [entry.to_mapping() for entry in self.entries],
        }
