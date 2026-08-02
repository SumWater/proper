"""Strict observable-input boundary for PROPER v2.3 execution contracts."""

from __future__ import annotations

from typing import Any, Mapping

from ..boundary import assert_observable_payload
from ..contracts import DecisionPhase
from .contracts import (
    ActionEffectContract,
    ActionPurpose,
    ActionSpec,
    ControllerDisposition,
    EvidenceRecord,
    EvidenceSource,
    ExecutionStatus,
)
from .ledger import ActionExecutionLedger, LedgerEntry


V2_3_FORBIDDEN_INPUT_KEYS = frozenset(
    {
        "scenario_name",
        "semantic_family",
        "gold_action",
        "gold_label",
        "evaluator_outcome",
        "prior_model_result",
        "model_outcome",
    }
)


def _assert_v2_3_specific_keys(value: Any, path: str) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).lower()
            if normalized in V2_3_FORBIDDEN_INPUT_KEYS:
                raise ValueError(f"forbidden PROPER v2.3 input at {path}.{key}")
            _assert_v2_3_specific_keys(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _assert_v2_3_specific_keys(child, f"{path}[{index}]")


def assert_v2_3_observable_payload(value: Any, path: str = "$") -> None:
    assert_observable_payload(value, path)
    _assert_v2_3_specific_keys(value, path)


def observable_action_from_mapping(payload: Mapping[str, Any]) -> ActionSpec:
    assert_v2_3_observable_payload(payload)
    return ActionSpec.from_mapping(payload)


def action_effect_contract_from_mapping(
    payload: Mapping[str, Any],
) -> ActionEffectContract:
    assert_v2_3_observable_payload(payload)
    return ActionEffectContract.from_mapping(payload)


def execution_ledger_from_mapping(payload: Mapping[str, Any]) -> ActionExecutionLedger:
    """Reconstruct a complete ledger after enforcing the observable boundary."""

    assert_v2_3_observable_payload(payload)
    entries = []
    for item in payload["entries"]:
        if not isinstance(item.get("decision_allowed"), bool):
            raise ValueError("serialized decision_allowed must be boolean")
        action = ActionSpec.from_mapping(item["action"])
        claimed_identity = item["action"].get("normalized_identity")
        if claimed_identity is not None and claimed_identity != action.identity:
            raise ValueError("serialized action identity does not match canonical action")
        evidence = tuple(
            EvidenceRecord(
                source=EvidenceSource(record["source"]),
                code=str(record["code"]),
                observed_at_step=int(record["observed_at_step"]),
            )
            for record in item.get("evidence", ())
        )
        entries.append(
            LedgerEntry(
                entry_id=str(item["entry_id"]),
                sequence_index=int(item["sequence_index"]),
                action=action,
                effect_contract=ActionEffectContract.from_mapping(
                    item["effect_contract"]
                ),
                phase=DecisionPhase(item["phase"]),
                purpose=ActionPurpose(item["purpose"]),
                status=ExecutionStatus(item["status"]),
                controller_disposition=ControllerDisposition(
                    item["controller_disposition"]
                ),
                decision_allowed=item["decision_allowed"],
                reason_codes=tuple(item["reason_codes"]),
                related_entry_ids=tuple(item.get("related_entry_ids", ())),
                evidence=evidence,
            )
        )
    return ActionExecutionLedger(
        trajectory_id=str(payload["trajectory_id"]), entries=tuple(entries)
    )
