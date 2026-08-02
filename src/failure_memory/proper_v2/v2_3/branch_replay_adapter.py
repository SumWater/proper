"""Split-state environment adapter for identical-start branch replay.

The adapter is intentionally independent of tau3 imports.  It can wrap a tau3
Environment at runtime, but unit tests use a fake environment.  The default
orchestrator may pass the complete public history to ``set_state``; this adapter
validates that history, restores the evaluator checkpoint, and forwards an
empty mutation-replay history to the wrapped environment.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

from .branch_capture import canonical_sha256


class BranchReplayIntegrityError(RuntimeError):
    pass


class SplitStateEnvironmentAdapter:
    def __init__(
        self,
        environment: Any,
        replay_plan: Mapping[str, Any],
        *,
        checkpoint_builder: Callable[[Mapping[str, Any]], Any] = lambda value: value,
        checkpoint_exporter: Callable[[Any], Mapping[str, Any]] | None = None,
        history_serializer: Callable[[Sequence[Any]], Sequence[Mapping[str, Any]]] = lambda value: value,
    ) -> None:
        self._environment = environment
        self._plan = dict(replay_plan)
        self._checkpoint_builder = checkpoint_builder
        self._checkpoint_exporter = checkpoint_exporter
        self._history_serializer = history_serializer
        self._initialized = False
        if self._plan.get("environment_replay_history") != []:
            raise BranchReplayIntegrityError("complete checkpoint requires empty environment replay history")
        if canonical_sha256(self._plan["environment_initialization"]) != self._plan["checkpoint_sha256"]:
            raise BranchReplayIntegrityError("checkpoint payload does not match checkpoint digest")

    @property
    def wrapped_environment(self) -> Any:
        return self._environment

    @property
    def initialized(self) -> bool:
        return self._initialized

    def set_state(
        self,
        initialization_data: Any,
        initialization_actions: Any,
        message_history: Sequence[Any],
        strict: bool = True,
    ) -> None:
        if self._initialized:
            raise BranchReplayIntegrityError("branch environment can only be initialized once")
        if initialization_data is not None or initialization_actions is not None:
            raise BranchReplayIntegrityError("task initialization cannot be merged with a frozen branch checkpoint")
        serialized_history = list(self._history_serializer(message_history))
        if canonical_sha256(serialized_history) != canonical_sha256(self._plan["participant_message_history"]):
            raise BranchReplayIntegrityError("participant history does not match frozen branch start")
        checkpoint = self._checkpoint_builder(self._plan["environment_initialization"])
        self._environment.set_state(checkpoint, None, [], strict=strict)
        if self._checkpoint_exporter is not None:
            restored = self._checkpoint_exporter(self._environment)
            if canonical_sha256(restored) != self._plan["checkpoint_sha256"]:
                raise BranchReplayIntegrityError("restored environment does not match frozen checkpoint")
        self._initialized = True

    def __getattr__(self, name: str) -> Any:
        return getattr(self._environment, name)


def tau_initialization_data_builder(payload: Mapping[str, Any]) -> Any:
    """Build tau3 InitializationData lazily so local core tests need no tau install."""

    try:
        from tau2.data_model.tasks import InitializationData
    except ImportError as exc:
        raise RuntimeError("tau2-bench must be installed or added to PYTHONPATH") from exc
    return InitializationData.model_validate(payload)


def export_tau_initialization_data(environment: Any, template: Mapping[str, Any]) -> dict[str, Any]:
    """Export only checkpoint channels present in the frozen template."""

    exported: dict[str, Any] = {}
    if "agent_data" in template:
        if environment.tools is None or environment.tools.db is None:
            raise BranchReplayIntegrityError("agent database is unavailable")
        exported["agent_data"] = environment.tools.db.model_dump()
    if "user_data" in template:
        if environment.user_tools is None or environment.user_tools.db is None:
            raise BranchReplayIntegrityError("user database is unavailable")
        exported["user_data"] = environment.user_tools.db.model_dump()
    return exported


def make_tau_checkpoint_exporter(template: Mapping[str, Any]) -> Callable[[Any], Mapping[str, Any]]:
    return lambda environment: export_tau_initialization_data(environment, template)
