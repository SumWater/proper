"""Scenario-neutral public branch capture and identical-start replay planning.

The model-facing history and evaluator-side environment checkpoint are kept as
separate objects.  This is required when a non-idempotent call executed but its
result is unknown: participants must see the public unknown-outcome receipt,
while environment initialization must restore the post-call checkpoint without
executing that call again.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

FORBIDDEN_MODEL_KEYS = frozenset(
    {
        "task_id",
        "source_task_id",
        "evaluation_criteria",
        "gold_action",
        "gold_actions",
        "recoverability",
        "evaluator_outcome",
        "environment_checkpoint",
        "checkpoint_payload",
        "checkpoint_applied_call_ids",
    }
)
EFFECT_CLASSES = frozenset(
    {"read_only", "idempotent_state_setting", "non_idempotent_side_effect", "outcome_unknown"}
)
RECEIPT_KINDS = frozenset({"pre_action_trigger", "executed_failure", "outcome_unknown"})


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _find_forbidden_keys(value: Any, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if str(key).casefold() in FORBIDDEN_MODEL_KEYS:
                found.append(child_path)
            found.extend(_find_forbidden_keys(child, child_path))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            found.extend(_find_forbidden_keys(child, f"{path}[{index}]"))
    return found


def _tool_calls(history: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    calls: dict[str, Mapping[str, Any]] = {}
    for message in history:
        for call in message.get("tool_calls") or []:
            call_id = str(call.get("id", ""))
            if not call_id or call_id in calls:
                raise ValueError("tool-call ids must be present and unique")
            calls[call_id] = call
    return calls


def _tool_receipts(history: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    receipts: dict[str, Mapping[str, Any]] = {}
    for message in history:
        if message.get("role") != "tool":
            continue
        call_id = str(message.get("tool_call_id", ""))
        if not call_id or call_id in receipts:
            raise ValueError("tool receipts must reference one unique call id")
        receipts[call_id] = message
    return receipts


@dataclass(frozen=True)
class PublicBranchCapture:
    public_history: tuple[dict[str, Any], ...]
    effect_class: str
    receipt_kind: str
    guarded_call_id: str | None
    native_execution_observed: bool
    checkpoint_payload: dict[str, Any]
    checkpoint_applied_call_ids: tuple[str, ...]
    controller_state: dict[str, Any]

    def __post_init__(self) -> None:
        if self.effect_class not in EFFECT_CLASSES:
            raise ValueError(f"unsupported effect class: {self.effect_class}")
        if self.receipt_kind not in RECEIPT_KINDS:
            raise ValueError(f"unsupported receipt kind: {self.receipt_kind}")
        forbidden = _find_forbidden_keys(self.public_history)
        if forbidden:
            raise ValueError(f"forbidden evaluator metadata in public history: {forbidden}")
        calls = _tool_calls(self.public_history)
        receipts = _tool_receipts(self.public_history)
        for call_id in receipts:
            if call_id not in calls:
                raise ValueError(f"receipt without public tool call: {call_id}")
        if self.receipt_kind == "pre_action_trigger":
            if self.guarded_call_id is not None or self.native_execution_observed:
                raise ValueError("pre-action capture cannot claim a guarded execution")
        else:
            if not self.guarded_call_id or self.guarded_call_id not in calls:
                raise ValueError("post-failure capture requires the guarded public tool call")
            if self.guarded_call_id not in receipts:
                raise ValueError("post-failure capture requires a public tool receipt")
        applied = set(self.checkpoint_applied_call_ids)
        if len(applied) != len(self.checkpoint_applied_call_ids):
            raise ValueError("checkpoint-applied call ids must be unique")
        if not applied.issubset(calls):
            raise ValueError("checkpoint-applied calls must exist in public history")
        if self.native_execution_observed and self.guarded_call_id not in applied:
            raise ValueError("executed guarded call must be represented in the checkpoint")
        if not self.native_execution_observed and self.guarded_call_id in applied:
            raise ValueError("non-executed guarded call cannot be checkpoint-applied")
        if self.receipt_kind == "outcome_unknown" and not self.native_execution_observed:
            raise ValueError("unknown outcome requires observed native execution")

    @property
    def checkpoint_sha256(self) -> str:
        return canonical_sha256(self.checkpoint_payload)

    def method_view(self) -> dict[str, Any]:
        view = {
            "schema_version": 1,
            "public_history": copy.deepcopy(list(self.public_history)),
            "effect_class": self.effect_class,
            "receipt_kind": self.receipt_kind,
            "controller_state": copy.deepcopy(self.controller_state),
        }
        forbidden = _find_forbidden_keys(view)
        if forbidden:
            raise ValueError(f"method view contains evaluator-only fields: {forbidden}")
        return view

    def evaluator_record(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "method_view": self.method_view(),
            "environment_checkpoint": copy.deepcopy(self.checkpoint_payload),
            "checkpoint_sha256": self.checkpoint_sha256,
            "checkpoint_applied_call_ids": list(self.checkpoint_applied_call_ids),
            "guarded_call_id": self.guarded_call_id,
            "native_execution_observed": self.native_execution_observed,
        }

    def replay_plan(self) -> dict[str, Any]:
        """Return split histories for a runtime adapter.

        The participant history is complete.  Environment replay history is
        empty because the checkpoint already represents the complete state at
        the branch boundary; replaying earlier mutations would duplicate them.
        """

        return {
            "schema_version": 1,
            "participant_message_history": copy.deepcopy(list(self.public_history)),
            "environment_initialization": copy.deepcopy(self.checkpoint_payload),
            "environment_replay_history": [],
            "skip_environment_replay_call_ids": sorted(_tool_calls(self.public_history)),
            "checkpoint_sha256": self.checkpoint_sha256,
            "identical_start_sha256": canonical_sha256(
                {
                    "public_history": self.public_history,
                    "checkpoint_sha256": self.checkpoint_sha256,
                    "controller_state": self.controller_state,
                }
            ),
        }


def assert_identical_starts(
    capture: PublicBranchCapture, condition_names: Iterable[str]
) -> dict[str, str]:
    names = tuple(condition_names)
    if not names or len(set(names)) != len(names):
        raise ValueError("condition names must be non-empty and unique")
    digest = capture.replay_plan()["identical_start_sha256"]
    return {name: digest for name in names}
