"""Agent-boundary instrumentation without modifying the benchmark package."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Mapping


INJECTION_ONLY_DETAIL_KEYS = frozenset({"faults", "original_error_code"})


def _sanitize_error(error: Any) -> Any:
    if not isinstance(error, dict):
        return deepcopy(error)
    cleaned = deepcopy(error)
    details = cleaned.get("details")
    if isinstance(details, dict):
        cleaned["details"] = {
            key: value for key, value in details.items() if key not in INJECTION_ONLY_DETAIL_KEYS
        }
    return cleaned


def sanitize_observation_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Remove evaluator-only injection metadata while preserving operational feedback.

    The sanitizer is deliberately narrow: it does not hide error codes, messages,
    retry budgets, schemas, or ordinary error details. It removes only fields that
    ToolMisuseBench itself adds to expose its injection event/original hidden error.
    """

    cleaned = deepcopy(dict(payload))
    transcript = cleaned.get("transcript")
    if isinstance(transcript, list):
        sanitized_entries: list[Any] = []
        for item in transcript:
            if not isinstance(item, dict):
                sanitized_entries.append(deepcopy(item))
                continue
            entry = deepcopy(item)
            entry["error"] = _sanitize_error(entry.get("error"))
            output = entry.get("output")
            if isinstance(output, dict):
                entry["output"] = {
                    key: value for key, value in output.items() if key != "faults"
                }
            sanitized_entries.append(entry)
        cleaned["transcript"] = sanitized_entries
    cleaned["last_error"] = _sanitize_error(cleaned.get("last_error"))
    return cleaned


def contains_injection_metadata(value: Any) -> bool:
    """Return whether sanitized agent-visible data still contains injection keys."""

    if isinstance(value, dict):
        if INJECTION_ONLY_DETAIL_KEYS.intersection(value):
            return True
        return any(contains_injection_metadata(child) for child in value.values())
    if isinstance(value, list):
        return any(contains_injection_metadata(child) for child in value)
    return False


@dataclass
class AgentBoundaryRecorder:
    """Sanitize observations and retain the agent's original actions out of band."""

    delegate: Any
    raw_observations: list[dict[str, Any]] = field(default_factory=list)
    sanitized_observations: list[dict[str, Any]] = field(default_factory=list)
    original_actions: list[dict[str, Any] | None] = field(default_factory=list)
    stop_reasons: list[str | None] = field(default_factory=list)

    def reset(self) -> None:
        self.raw_observations.clear()
        self.sanitized_observations.clear()
        self.original_actions.clear()
        self.stop_reasons.clear()
        self.delegate.reset()

    def act(self, observation: Any) -> Any:
        raw = observation.model_dump(mode="json")
        sanitized_payload = sanitize_observation_payload(raw)
        sanitized = observation.__class__.model_validate(sanitized_payload)
        self.raw_observations.append(raw)
        self.sanitized_observations.append(sanitized_payload)
        action = self.delegate.act(sanitized)
        self.original_actions.append(
            action.model_dump(mode="json") if action is not None else None
        )
        reason = getattr(self.delegate, "last_stop_reason", None) if action is None else None
        self.stop_reasons.append(reason if isinstance(reason, str) else None)
        return action

