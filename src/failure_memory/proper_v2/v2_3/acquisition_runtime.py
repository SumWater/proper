"""Executable acquisition loop with injected worker and environment ports."""

from __future__ import annotations

import json
import queue
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from .acquisition_participants import (
    canonical_json,
    make_worker_request,
    parse_agent_output,
    parse_user_output,
    render_agent_system_prompt,
    render_user_system_prompt,
    serialize_agent_history,
    serialize_user_history,
)
from .acquisition_runtime_protocol import AcquisitionProtocolMachine, canonical_sha256


class WorkerPort(Protocol):
    def complete(self, request: Mapping[str, Any]) -> Mapping[str, Any]: ...


class EnvironmentPort(Protocol):
    def checkpoint(self) -> Mapping[str, Any]: ...
    def execute(self, tool_name: str, arguments: Mapping[str, Any], effect_class: str) -> "EnvironmentExecution": ...


@dataclass(frozen=True)
class EnvironmentExecution:
    content: Any
    error: bool
    outcome: str
    native_executed: bool = True


@dataclass(frozen=True)
class AttemptSpec:
    attempt_ordinal: int
    evaluator_pair_id: str
    phase: str
    target_tool_name: str
    target_effect_class: str
    public_policy: str
    public_tools: Sequence[Mapping[str, Any]]
    simulation_guidelines: str
    private_user_scenario: Mapping[str, Any]
    action_registry: Mapping[str, str]


class JsonlSubprocessWorker:
    """Sequential persistent JSONL transport with bounded response waiting."""

    def __init__(self, command: Sequence[str], *, stderr_path: Path, timeout_seconds: float) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.command = list(command)
        self.stderr_path = stderr_path
        self.timeout_seconds = timeout_seconds
        self.process: subprocess.Popen[str] | None = None
        self._stderr_stream: Any = None
        self._responses: queue.Queue[str | None] = queue.Queue()
        self._reader: threading.Thread | None = None

    def __enter__(self) -> "JsonlSubprocessWorker":
        self.stderr_path.parent.mkdir(parents=True, exist_ok=True)
        self._stderr_stream = self.stderr_path.open("w", encoding="utf-8", newline="\n")
        self.process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self._stderr_stream,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        self._reader = threading.Thread(target=self._read_stdout, daemon=True)
        self._reader.start()
        return self

    def _read_stdout(self) -> None:
        assert self.process is not None and self.process.stdout is not None
        for line in self.process.stdout:
            self._responses.put(line)
        self._responses.put(None)

    def complete(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        if self.process is None or self.process.stdin is None:
            raise RuntimeError("worker is not running")
        if self.process.poll() is not None:
            raise RuntimeError(f"worker exited before request: {self.process.returncode}")
        self.process.stdin.write(canonical_json(dict(request)) + "\n")
        self.process.stdin.flush()
        try:
            line = self._responses.get(timeout=self.timeout_seconds)
        except queue.Empty as exc:
            raise TimeoutError("worker response timeout") from exc
        if line is None:
            raise RuntimeError(f"worker stdout closed: {self.process.poll()}")
        response = json.loads(line)
        if not isinstance(response, Mapping):
            raise ValueError("worker response must be an object")
        return response

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if self.process is not None:
            if self.process.stdin is not None:
                self.process.stdin.close()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                self.process.wait(timeout=5)
            if self._reader is not None:
                self._reader.join(timeout=5)
            if self.process.stdout is not None:
                self.process.stdout.close()
        if self._stderr_stream is not None:
            self._stderr_stream.close()


def _validated_worker_response(
    response: Mapping[str, Any], request_id: str, *, require_synthetic: bool
) -> tuple[str, Mapping[str, Any]]:
    if response.get("request_id") != request_id:
        raise ValueError("worker response request_id mismatch")
    if response.get("ok") is not True:
        raise RuntimeError(str(response.get("error") or "worker returned ok=false"))
    if bool(response.get("synthetic_non_model_output")) != require_synthetic:
        raise ValueError("worker synthetic/model boundary mismatch")
    raw_text, usage = response.get("raw_text"), response.get("usage")
    if not isinstance(raw_text, str) or not isinstance(usage, Mapping):
        raise ValueError("worker response lacks raw_text or usage")
    return raw_text, usage


def run_attempt(
    spec: AttemptSpec,
    *,
    prompt_config: Mapping[str, Any],
    budgets: Mapping[str, Any],
    worker: WorkerPort,
    environment: EnvironmentPort,
    require_synthetic: bool,
) -> dict[str, Any]:
    machine = AcquisitionProtocolMachine(
        phase=spec.phase,
        target_tool_name=spec.target_tool_name,
        target_effect_class=spec.target_effect_class,
        action_registry=spec.action_registry,
        maximum_steps=int(budgets["maximum_orchestrator_steps_per_pair"]),
        maximum_tool_errors=int(budgets["maximum_tool_errors_per_pair"]),
        maximum_agent_requests=int(budgets["maximum_agent_requests_per_pair"]),
        maximum_user_requests=int(budgets["maximum_user_requests_per_pair"]),
        maximum_prompt_tokens_per_request=int(budgets["maximum_prompt_tokens_per_request_observed_stop"]),
        maximum_total_prompt_tokens=int(budgets["maximum_total_prompt_tokens_per_pair_observed_stop"]),
        maximum_total_completion_tokens=int(budgets["maximum_total_completion_tokens_per_pair"]),
    )
    agent_system = render_agent_system_prompt(
        prompt_config, public_policy=spec.public_policy, public_tools=spec.public_tools
    )
    user_system = render_user_system_prompt(
        prompt_config,
        simulation_guidelines=spec.simulation_guidelines,
        private_scenario=canonical_json(spec.private_user_scenario),
    )
    generation = prompt_config["generation_contract"]
    request_counts = {"agent": 0, "user": 0}
    worker_records: list[dict[str, Any]] = []
    runtime_errors: list[str] = []
    checkpoint_payload: Mapping[str, Any] | None = None

    while machine.status == "active":
        actor = machine.next_actor
        if actor in {"user", "agent"}:
            request_counts[actor] += 1
            request_id = f"attempt-{spec.attempt_ordinal:02d}:{actor}:{request_counts[actor]:04d}"
            messages = (
                serialize_user_history(user_system, machine.public_history)
                if actor == "user"
                else serialize_agent_history(agent_system, machine.public_history)
            )
            request = make_worker_request(
                request_id=request_id,
                messages=messages,
                seed=int(generation["seed"]),
                max_new_tokens=int(generation["max_new_tokens"]),
            )
            try:
                response = worker.complete(request)
                raw_text, usage = _validated_worker_response(
                    response, request_id, require_synthetic=require_synthetic
                )
                worker_records.append({
                    "participant": actor,
                    "request_id": request_id,
                    "request_sha256": canonical_sha256(request),
                    "raw_text": raw_text,
                    "usage": dict(usage),
                    "synthetic_non_model_output": require_synthetic,
                })
            except Exception as exc:
                worker_records.append({
                    "participant": actor, "request_id": request_id,
                    "error": f"{type(exc).__name__}: {exc}",
                    "synthetic_non_model_output": require_synthetic,
                })
                machine.record_worker_error(actor)
                continue
            try:
                decision = parse_user_output(raw_text) if actor == "user" else parse_agent_output(raw_text, spec.public_tools)
            except ValueError as exc:
                worker_records[-1]["parse_error"] = f"{type(exc).__name__}: {exc}"
                machine.record_invalid_output(actor)
                continue
            if actor == "user":
                machine.record_user_message(decision["content"], usage)
                if machine.status == "captured":
                    try:
                        checkpoint_payload = environment.checkpoint()
                        machine.checkpoint_sha256 = canonical_sha256(checkpoint_payload)
                    except Exception as exc:
                        runtime_errors.append(f"checkpoint:{type(exc).__name__}: {exc}")
                        machine._fail("environment_checkpoint_error", status="infrastructure_failure")
                continue
            pre_checkpoint_hash = None
            if (
                decision["kind"] == "tool"
                and decision["tool_name"] == spec.target_tool_name
                and spec.target_effect_class == "idempotent_state_setting"
            ):
                try:
                    checkpoint_payload = environment.checkpoint()
                    pre_checkpoint_hash = canonical_sha256(checkpoint_payload)
                except Exception as exc:
                    runtime_errors.append(f"checkpoint:{type(exc).__name__}: {exc}")
                    machine._fail("environment_checkpoint_error", status="infrastructure_failure")
                    continue
            machine.record_agent_decision(
                decision, usage, pre_action_checkpoint_sha256=pre_checkpoint_hash
            )
            continue

        if actor in {"environment", "target_environment"}:
            pending = machine.pending_call
            if pending is None:
                machine._fail("missing_pending_call")
                continue
            try:
                execution = environment.execute(
                    pending["tool_name"], pending["arguments"], pending["effect_class"]
                )
            except Exception as exc:
                runtime_errors.append(f"execute:{type(exc).__name__}: {exc}")
                machine._fail("environment_execution_error", status="infrastructure_failure")
                continue
            post_checkpoint_hash = None
            if actor == "target_environment" or (
                execution.outcome == "unknown" and pending["effect_class"] != "read_only"
            ):
                try:
                    checkpoint_payload = environment.checkpoint()
                    post_checkpoint_hash = canonical_sha256(checkpoint_payload)
                except Exception as exc:
                    runtime_errors.append(f"checkpoint:{type(exc).__name__}: {exc}")
                    machine._fail("environment_checkpoint_error", status="infrastructure_failure")
                    continue
            machine.record_environment_result(
                content=execution.content,
                error=execution.error,
                outcome=execution.outcome,
                native_executed=execution.native_executed,
                post_action_checkpoint_sha256=post_checkpoint_hash,
            )
            if (
                actor == "environment"
                and execution.outcome == "unknown"
                and pending["effect_class"] != "read_only"
                and machine.status == "active"
            ):
                machine.public_history[-1] = {
                    "role": "tool", "tool_call_id": pending["call_id"], "error": True,
                    "content": {
                        "code": "result_unknown", "outcome": "unknown",
                        "retry_safe": False, "verification_required": True,
                    },
                }
                machine.checkpoint_sha256 = post_checkpoint_hash
                machine._fail("ambiguous_non_target_tool_outcome")
            continue
        machine._fail("invalid_runtime_actor", status="infrastructure_failure")

    return {
        "evaluator_pair_id": spec.evaluator_pair_id,
        "attempt_ordinal": spec.attempt_ordinal,
        "phase": spec.phase,
        "target_effect_class": spec.target_effect_class,
        "target_tool_name": spec.target_tool_name,
        "public_state": machine.public_snapshot(),
        "environment_checkpoint": checkpoint_payload,
        "worker_records": worker_records,
        "runtime_errors": runtime_errors,
        "synthetic_non_model_output": require_synthetic,
    }


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes((json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    temporary.replace(path)


def run_stage(
    specs: Sequence[AttemptSpec],
    *,
    prompt_config: Mapping[str, Any],
    budgets: Mapping[str, Any],
    worker: WorkerPort,
    environment_factory: Any,
    run_directory: Path,
    require_synthetic: bool,
) -> dict[str, Any]:
    run_directory.mkdir(parents=True, exist_ok=False)
    attempts: list[dict[str, Any]] = []
    for spec in specs:
        result = run_attempt(
            spec,
            prompt_config=prompt_config,
            budgets=budgets,
            worker=worker,
            environment=environment_factory(spec),
            require_synthetic=require_synthetic,
        )
        attempts.append(result)
        _atomic_json(run_directory / f"attempt-{spec.attempt_ordinal:02d}.json", result)
        if result["public_state"]["status"] != "captured":
            break
    summary = {
        "attempts_requested": len(specs),
        "attempts_written": len(attempts),
        "captured": sum(item["public_state"]["status"] == "captured" for item in attempts),
        "stopped_after_first_failure": len(attempts) < len(specs),
        "passed": len(attempts) == len(specs) and all(
            item["public_state"]["status"] == "captured" for item in attempts
        ),
        "attempts": attempts,
        "synthetic_non_model_output": require_synthetic,
    }
    _atomic_json(run_directory / "stage.json", summary)
    return summary
