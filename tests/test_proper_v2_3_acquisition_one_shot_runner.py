from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "experiments/proper_v2_3/run_tau3_acquisition_remote_v2_3.py"
SPEC = importlib.util.spec_from_file_location("proper_v2_3_acquisition_runner", RUNNER_PATH)
assert SPEC and SPEC.loader
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class ScriptedWorker:
    def __init__(self, candidates: list[dict[str, Any]], fail_ordinal: int | None = None) -> None:
        self.candidates = candidates
        self.fail_ordinal = fail_ordinal
        self.requests: list[dict[str, Any]] = []

    def complete(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        value = dict(request)
        self.requests.append(value)
        ordinal = int(str(value["request_id"]).split(":", 1)[0].split("-")[1])
        actor = str(value["request_id"]).split(":")[1]
        if actor == "user":
            raw = json.dumps({"kind":"message","content":f"synthetic request {ordinal}"})
        elif self.fail_ordinal == ordinal:
            raw = "not-json"
        else:
            raw = json.dumps({"kind":"tool","tool_name":self.candidates[ordinal - 1]["guarded_action_name"],"arguments":{}})
        return {"request_id":value["request_id"],"ok":True,"raw_text":raw,"usage":{"prompt_token_count":7,"completion_token_count":5},"synthetic_non_model_output":True}


class FakeEnvironment:
    def __init__(self) -> None:
        self.executions = 0

    def checkpoint(self) -> Mapping[str, Any]:
        return {"agent_data":{"executions":self.executions}}

    def execute(self, tool_name: str, arguments: Mapping[str, Any], effect_class: str) -> Any:
        self.executions += 1
        return runner.EnvironmentExecution(content={"ok":True},error=False,outcome="succeeded",native_executed=True)


def fixtures() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, str]]]:
    protocol = runner.load_object(runner.PROTOCOL_CONFIG)
    candidates = runner.candidate_records(runner.load_object(runner.CANDIDATE_CONFIG), protocol["execution"]["capture_order"])
    tasks = {item["pair_id"]:{"domain":item["domain"],"task":{"initial_state":None,"user_scenario":{"instructions":{"reason_for_call":"synthetic only"}}}} for item in candidates}
    registries = runner.action_registries(runner.load_object(runner.EFFECT_CONFIG))
    return candidates, tasks, registries


def environment_builder(*, root: Path, domain: str, raw_task: Mapping[str, Any]) -> tuple[Any, str, list[dict[str, Any]]]:
    del root, domain, raw_task
    candidates, _, _ = fixtures()
    tools = [{"name":item["guarded_action_name"],"description":"synthetic public tool","parameters":{"type":"object","properties":{},"required":[],"additionalProperties":False}} for item in candidates]
    return FakeEnvironment(), "Synthetic public policy.", tools


class OneShotAcquisitionRunnerTests(unittest.TestCase):
    def test_import_is_lazy_for_tau_and_model_libraries(self) -> None:
        source = RUNNER_PATH.read_text(encoding="utf-8")
        top_level = source.split("def collect_real_preflight", 1)[0]
        self.assertNotIn("import torch", top_level)
        self.assertNotIn("import transformers", top_level)
        self.assertNotIn("from tau2", top_level)
        self.assertFalse(any(name == "tau2" or name.startswith("tau2.") for name in sys.modules))

    def test_all_twelve_frozen_task_components_verify(self) -> None:
        tasks = runner.load_and_verify_tasks(runner.load_object(runner.RUNTIME_CONFIG))
        self.assertEqual(len(tasks), 12)
        self.assertTrue(all(item["task"]["initial_state"] is None for item in tasks.values()))

    def test_preflight_fails_closed_on_each_missing_observation(self) -> None:
        keys = list(runner.evaluate_preflight_observation({}).keys())
        for missing in keys:
            observed = {key: True for key in keys}
            observed[missing] = False
            checks = runner.evaluate_preflight_observation(observed)
            self.assertFalse(all(checks.values()), missing)

    def test_full_synthetic_orchestration_writes_twelve_atomic_attempts(self) -> None:
        candidates, tasks, registries = fixtures()
        worker = ScriptedWorker(candidates)
        prompts = runner.load_object(runner.PROMPT_CONFIG)
        budgets = runner.load_object(runner.RUNTIME_CONFIG)["budgets"]
        progress: list[int] = []
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            attempts, records, status, reason = runner.execute_prepared_attempts(
                output_directory=output,candidates=candidates,tasks=tasks,prompts=prompts,budgets=budgets,registries=registries,guidelines="Synthetic guidelines.",worker=worker,environment_builder=environment_builder,require_synthetic=True,progress_callback=lambda a, r, s, x: progress.append(len(a)),
            )
            self.assertEqual((len(attempts),len(records),status,reason),(12,12,"completed",None))
            self.assertEqual(progress,list(range(1,13)))
            self.assertEqual(len(list((output / "attempts").glob("attempt-*.json"))),12)
            self.assertFalse(list(output.rglob("*.tmp")))
            self.assertTrue(all(item["target_native_execution_count"] <= 1 for item in records))
            self.assertTrue(all("tau3-dev" not in json.dumps(request["messages"]) for request in worker.requests))

    def test_invalid_fifth_attempt_stops_without_sixth_attempt(self) -> None:
        candidates, tasks, registries = fixtures()
        worker = ScriptedWorker(candidates, fail_ordinal=5)
        with tempfile.TemporaryDirectory() as temporary:
            attempts, records, status, reason = runner.execute_prepared_attempts(
                output_directory=Path(temporary),candidates=candidates,tasks=tasks,prompts=runner.load_object(runner.PROMPT_CONFIG),budgets=runner.load_object(runner.RUNTIME_CONFIG)["budgets"],registries=registries,guidelines="Synthetic guidelines.",worker=worker,environment_builder=environment_builder,require_synthetic=True,
            )
        self.assertEqual(len(attempts),5)
        self.assertEqual(len(records),5)
        self.assertEqual(status,"capture_stopped")
        self.assertEqual(reason,"invalid_agent_output")
        self.assertFalse(any(str(request["request_id"]).startswith("attempt-06") for request in worker.requests))

    def test_v2_schema_separates_complete_and_target_execution_counts(self) -> None:
        schema = runner.load_object(ROOT / "schemas/proper_v2_3/real_public_branch_capture_run_v2.schema.json")
        item = schema["properties"]["attempt_artifacts"]["items"]["properties"]
        self.assertNotIn("maximum", item["native_tool_execution_count"])
        self.assertEqual(item["target_native_execution_count"]["maximum"],1)
        config = runner.load_object(runner.IMPLEMENTATION_CONFIG)
        self.assertFalse(config["pre_model_schema_correction"]["modify_v1"])
        self.assertEqual(runner.sha256(ROOT / config["pre_model_schema_correction"]["frozen_v1_path"]),config["pre_model_schema_correction"]["frozen_v1_sha256"])

    def test_envelope_keeps_development_and_confirmatory_boundaries(self) -> None:
        result = runner.build_envelope(project_revision="1"*40,attempts=[],artifact_records=[],status="preflight_failed",stop_reason="fixture",preflight_seconds=1.0,startup_seconds=0.0,run_seconds=1.0)
        self.assertEqual(result["next_gate"],"stop_and_preserve_acquisition_result")
        self.assertFalse(result["boundary"]["heldout"])
        self.assertFalse(result["boundary"]["confirmatory"])
        self.assertFalse(result["boundary"]["model_loaded"])
        self.assertEqual(result["capture_attempt_count"],0)


if __name__ == "__main__":
    unittest.main()
