"""End-to-end synthetic CPU dry-run of the acquisition runtime."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
PROMPTS = ROOT / "configs/proper_v2_3/local_tau_participant_prompts_v2_3.json"
PROTOCOL = ROOT / "configs/proper_v2_3/acquisition_runtime_protocol_v2_3.json"
SYNTHETIC_WORKER = ROOT / "experiments/proper_v2_3/synthetic_acquisition_jsonl_worker_v2_3.py"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.failure_memory.proper_v2.v2_3.acquisition_runtime import (
    AttemptSpec,
    EnvironmentExecution,
    JsonlSubprocessWorker,
    run_attempt,
    run_stage,
)
from src.failure_memory.proper_v2.v2_3.acquisition_runtime_protocol import canonical_sha256

REGISTRY = {
    "read_value": "read_only",
    "set_value": "idempotent_state_setting",
    "send_value": "non_idempotent_side_effect",
}
TOOLS = [
    {
        "name": name, "description": f"Synthetic {name} contract.",
        "parameters": {
            "type":"object", "additionalProperties":False,
            "required":["value"], "properties":{"value":{"type":"integer"}},
        },
    }
    for name in REGISTRY
]


class RecordingWorker:
    def __init__(self, wrapped: JsonlSubprocessWorker) -> None:
        self.wrapped = wrapped
        self.requests: list[dict[str, Any]] = []

    def complete(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        self.requests.append(copy.deepcopy(dict(request)))
        return self.wrapped.complete(request)


class SyntheticEnvironment:
    def __init__(self, *, ambiguous_set: bool = False) -> None:
        self.state = {"value":0,"sent":[]}
        self.native_calls: list[str] = []
        self.ambiguous_set = ambiguous_set

    def checkpoint(self) -> Mapping[str, Any]:
        return {"agent_data": copy.deepcopy(self.state)}

    def execute(self, tool_name: str, arguments: Mapping[str, Any], effect_class: str) -> EnvironmentExecution:
        self.native_calls.append(tool_name)
        if tool_name == "read_value":
            return EnvironmentExecution(content={"value":self.state["value"]}, error=False, outcome="succeeded")
        if tool_name == "set_value":
            self.state["value"] = int(arguments["value"])
            if self.ambiguous_set:
                return EnvironmentExecution(content={"native_error":"unknown"}, error=True, outcome="unknown")
            return EnvironmentExecution(content={"value":self.state["value"]}, error=False, outcome="succeeded")
        if tool_name == "send_value":
            self.state["sent"].append(int(arguments["value"]))
            return EnvironmentExecution(content={"secret_native_delivery_id":"d1"}, error=False, outcome="succeeded")
        raise ValueError(f"unknown synthetic tool: {tool_name}")


def spec(ordinal: int, phase: str, target: str, effect: str) -> AttemptSpec:
    return AttemptSpec(
        attempt_ordinal=ordinal,
        evaluator_pair_id=f"synthetic-evaluator-{ordinal}",
        phase=phase,
        target_tool_name=target,
        target_effect_class=effect,
        public_policy="SYNTHETIC_PUBLIC_POLICY_ONLY",
        public_tools=TOOLS,
        simulation_guidelines="Synthetic user guidelines.",
        private_user_scenario={"instructions":"SYNTHETIC_PRIVATE_SCENARIO_ONLY"},
        action_registry=REGISTRY,
    )


def run() -> dict[str, Any]:
    prompts = json.loads(PROMPTS.read_text(encoding="utf-8"))
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    budgets = protocol["budgets"]
    with tempfile.TemporaryDirectory() as raw:
        temporary = Path(raw)
        stderr_path = temporary / "synthetic_worker.stderr"
        command = [sys.executable, str(SYNTHETIC_WORKER)]
        with JsonlSubprocessWorker(command, stderr_path=stderr_path, timeout_seconds=5) as transport:
            worker = RecordingWorker(transport)
            environments: dict[int, SyntheticEnvironment] = {}

            def environment_factory(item: AttemptSpec) -> SyntheticEnvironment:
                environment = SyntheticEnvironment()
                environments[item.attempt_ordinal] = environment
                return environment

            success_specs = (
                spec(1, "pre_action", "read_value", "read_only"),
                spec(2, "post_failure", "set_value", "idempotent_state_setting"),
                spec(3, "post_failure", "send_value", "non_idempotent_side_effect"),
            )
            stage = run_stage(
                success_specs,
                prompt_config=prompts,
                budgets=budgets,
                worker=worker,
                environment_factory=environment_factory,
                run_directory=temporary / "successful-stage",
                require_synthetic=True,
            )
            invalid = run_attempt(
                spec(4, "post_failure", "set_value", "idempotent_state_setting"),
                prompt_config=prompts, budgets=budgets, worker=worker,
                environment=SyntheticEnvironment(), require_synthetic=True,
            )
            worker_error = run_attempt(
                spec(5, "pre_action", "read_value", "read_only"),
                prompt_config=prompts, budgets=budgets, worker=worker,
                environment=SyntheticEnvironment(), require_synthetic=True,
            )
            ambiguous = run_attempt(
                spec(6, "post_failure", "send_value", "non_idempotent_side_effect"),
                prompt_config=prompts, budgets=budgets, worker=worker,
                environment=SyntheticEnvironment(ambiguous_set=True), require_synthetic=True,
            )
            duplicate_environment = SyntheticEnvironment()
            duplicate = run_attempt(
                spec(7, "post_failure", "send_value", "non_idempotent_side_effect"),
                prompt_config=prompts, budgets=budgets, worker=worker,
                environment=duplicate_environment, require_synthetic=True,
            )
            persisted = sorted(path.name for path in (temporary / "successful-stage").glob("*.json"))
            stderr_text = stderr_path.read_text(encoding="utf-8")

        pre, setting, side_effect = stage["attempts"]
        all_agent_messages = [
            json.dumps(request["messages"], ensure_ascii=False)
            for request in worker.requests if ":agent:" in request["request_id"]
        ]
        all_user_messages = [
            json.dumps(request["messages"], ensure_ascii=False)
            for request in worker.requests if ":user:" in request["request_id"]
        ]
        checks = {
            "three_effect_class_stage_passed": stage["passed"] and stage["captured"] == 3,
            "attempt_artifacts_written_atomically": persisted == ["attempt-01.json","attempt-02.json","attempt-03.json","stage.json"],
            "pre_action_uses_actual_environment_checkpoint": pre["public_state"]["checkpoint_sha256"] == canonical_sha256({"agent_data":{"value":0,"sent":[]}}),
            "idempotent_target_suppressed": setting["public_state"]["target_native_execution_count"] == 0 and environments[2].native_calls == [],
            "non_idempotent_target_executed_once": side_effect["public_state"]["target_native_execution_count"] == 1 and environments[3].native_calls == ["send_value"],
            "non_idempotent_native_result_hidden": "secret_native_delivery_id" not in json.dumps(side_effect["public_state"], ensure_ascii=False),
            "invalid_json_preserved_without_retry": invalid["public_state"]["failure_reason"] == "invalid_agent_output" and len(invalid["worker_records"]) == 2,
            "worker_error_preserved": worker_error["public_state"]["status"] == "infrastructure_failure",
            "ambiguous_non_target_write_stops_with_checkpoint": ambiguous["public_state"]["failure_reason"] == "ambiguous_non_target_tool_outcome" and ambiguous["environment_checkpoint"] is not None,
            "duplicate_state_change_blocked_before_second_native_execution": duplicate["public_state"]["status"] == "safety_failure" and duplicate_environment.native_calls == ["set_value"],
            "agent_never_receives_private_scenario": all("SYNTHETIC_PRIVATE_SCENARIO_ONLY" not in value for value in all_agent_messages),
            "user_never_receives_domain_policy": all("SYNTHETIC_PUBLIC_POLICY_ONLY" not in value for value in all_user_messages),
            "worker_messages_exclude_evaluator_pair_ids": all("synthetic-evaluator" not in json.dumps(request["messages"]) for request in worker.requests),
            "all_worker_outputs_are_synthetic": all(item["synthetic_non_model_output"] for result in [*stage["attempts"],invalid,worker_error,ambiguous,duplicate] for item in result["worker_records"]),
            "synthetic_worker_stderr_empty": stderr_text == "",
        }
        return {
            "schema_version":1,
            "run_kind":"proper_v2_3_acquisition_runtime_synthetic_cpu_dry_run",
            "checks":checks,
            "passed":all(checks.values()),
            "successful_stage":stage,
            "deliberate_failures": {
                "invalid_output":invalid,
                "worker_error":worker_error,
                "ambiguous_non_target_write":ambiguous,
                "duplicate_state_change":duplicate,
            },
            "worker_request_count":len(worker.requests),
            "model_loaded":False,
            "model_outputs_read":False,
            "tau_imported":False,
            "task_executed":False,
            "gpu_used":False,
        }


def main() -> int:
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
