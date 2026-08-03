from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.proper_v2_3.run_acquisition_runtime_synthetic_cpu_v2_3 import (
    SyntheticEnvironment,
    run as run_dry,
    spec,
)
from src.failure_memory.proper_v2.v2_3.acquisition_runtime import (
    JsonlSubprocessWorker,
    _validated_worker_response,
    run_attempt,
    run_stage,
)
from src.failure_memory.proper_v2.v2_3.tau3_acquisition_runtime_adapter import (
    install_pinned_tau_namespace,
    normalize_public_tool_contracts,
)

PROMPTS = json.loads((ROOT / "configs/proper_v2_3/local_tau_participant_prompts_v2_3.json").read_text(encoding="utf-8"))
PROTOCOL = json.loads((ROOT / "configs/proper_v2_3/acquisition_runtime_protocol_v2_3.json").read_text(encoding="utf-8"))
WORKER = ROOT / "experiments/proper_v2_3/synthetic_acquisition_jsonl_worker_v2_3.py"


class StaticWorker:
    def __init__(self, raw_text: str) -> None:
        self.raw_text = raw_text

    def complete(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        return {
            "request_id": request["request_id"], "ok": True,
            "raw_text": self.raw_text,
            "usage":{"prompt_token_count":1,"completion_token_count":1},
            "synthetic_non_model_output":True,
        }


class FailingCheckpointEnvironment(SyntheticEnvironment):
    def checkpoint(self) -> Mapping[str, Any]:
        raise RuntimeError("deliberate checkpoint failure")


class AcquisitionRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dry = run_dry()

    def test_end_to_end_dry_run_passes_all_checks(self) -> None:
        self.assertTrue(self.dry["passed"])
        self.assertTrue(all(self.dry["checks"].values()))
        self.assertFalse(self.dry["model_loaded"])
        self.assertFalse(self.dry["task_executed"])

    def test_jsonl_transport_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            with JsonlSubprocessWorker(
                [sys.executable, str(WORKER)],
                stderr_path=Path(raw) / "stderr", timeout_seconds=5,
            ) as worker:
                response = worker.complete({
                    "request_id":"attempt-01:user:0001",
                    "messages":[{"role":"system","content":"s"}],
                    "seed":1,"max_new_tokens":1,
                })
            self.assertTrue(response["ok"])
            self.assertTrue(response["synthetic_non_model_output"])

    def test_worker_response_id_and_synthetic_boundary_are_strict(self) -> None:
        base = {
            "request_id":"other", "ok":True, "raw_text":"{}",
            "usage":{"prompt_token_count":0,"completion_token_count":0},
            "synthetic_non_model_output":True,
        }
        with self.assertRaisesRegex(ValueError, "request_id"):
            _validated_worker_response(base, "expected", require_synthetic=True)
        base["request_id"] = "expected"
        with self.assertRaisesRegex(ValueError, "boundary"):
            _validated_worker_response(base, "expected", require_synthetic=False)

    def test_stage_stops_and_persists_after_first_failed_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            with JsonlSubprocessWorker(
                [sys.executable, str(WORKER)], stderr_path=root / "stderr", timeout_seconds=5,
            ) as worker:
                stage = run_stage(
                    [
                        spec(4,"post_failure","set_value","idempotent_state_setting"),
                        spec(5,"pre_action","read_value","read_only"),
                    ],
                    prompt_config=PROMPTS, budgets=PROTOCOL["budgets"], worker=worker,
                    environment_factory=lambda _: SyntheticEnvironment(),
                    run_directory=root / "stage", require_synthetic=True,
                )
            self.assertEqual(stage["attempts_written"], 1)
            self.assertTrue(stage["stopped_after_first_failure"])
            self.assertEqual(sorted(path.name for path in (root / "stage").glob("*")), ["attempt-04.json","stage.json"])

    def test_atomic_persistence_leaves_no_temporary_file(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            with JsonlSubprocessWorker(
                [sys.executable, str(WORKER)], stderr_path=root / "stderr", timeout_seconds=5,
            ) as worker:
                run_stage(
                    [spec(1,"pre_action","read_value","read_only")],
                    prompt_config=PROMPTS, budgets=PROTOCOL["budgets"], worker=worker,
                    environment_factory=lambda _: SyntheticEnvironment(),
                    run_directory=root / "stage", require_synthetic=True,
                )
            self.assertEqual(list((root / "stage").glob("*.tmp")), [])

    def test_checkpoint_error_is_serialized_as_infrastructure_failure(self) -> None:
        result = run_attempt(
            spec(1,"pre_action","read_value","read_only"),
            prompt_config=PROMPTS, budgets=PROTOCOL["budgets"],
            worker=StaticWorker('{"kind":"message","content":"start"}'),
            environment=FailingCheckpointEnvironment(), require_synthetic=True,
        )
        self.assertEqual(result["public_state"]["status"], "infrastructure_failure")
        self.assertEqual(result["public_state"]["failure_reason"], "environment_checkpoint_error")
        self.assertEqual(len(result["runtime_errors"]), 1)

    def test_implementation_corrections_are_exercised(self) -> None:
        self.assertTrue(self.dry["checks"]["pre_action_uses_actual_environment_checkpoint"])
        self.assertTrue(self.dry["checks"]["ambiguous_non_target_write_stops_with_checkpoint"])

    def test_private_and_evaluator_fields_do_not_leak_to_wrong_worker(self) -> None:
        self.assertTrue(self.dry["checks"]["agent_never_receives_private_scenario"])
        self.assertTrue(self.dry["checks"]["user_never_receives_domain_policy"])
        self.assertTrue(self.dry["checks"]["worker_messages_exclude_evaluator_pair_ids"])

    def test_tau_adapter_import_is_lazy_in_fresh_python(self) -> None:
        code = (
            "import sys; import src.failure_memory.proper_v2.v2_3.tau3_acquisition_runtime_adapter; "
            "print('tau2' in sys.modules)"
        )
        completed = subprocess.run(
            [sys.executable, "-c", code], cwd=ROOT,
            check=True, capture_output=True, text=True,
        )
        self.assertEqual(completed.stdout.strip(), "False")

    def test_pinned_namespace_is_reusable_but_not_replaceable(self) -> None:
        existing = sys.modules.pop("tau2", None)
        try:
            with tempfile.TemporaryDirectory() as raw:
                source = Path(raw)
                (source / "tau2").mkdir()
                install_pinned_tau_namespace(source)
                install_pinned_tau_namespace(source)
                other = source / "other"
                (other / "tau2").mkdir(parents=True)
                with self.assertRaisesRegex(RuntimeError, "imported before"):
                    install_pinned_tau_namespace(other)
        finally:
            sys.modules.pop("tau2", None)
            if existing is not None:
                sys.modules["tau2"] = existing

    def test_public_tool_normalization_is_sorted_and_closed(self) -> None:
        def tool(name: str) -> Any:
            return types.SimpleNamespace(
                name=name,
                openai_schema={"function":{"name":name,"description":name,"parameters":{"type":"object"}}},
            )
        environment = types.SimpleNamespace(get_tools=lambda: [tool("z"),tool("a")])
        contracts = normalize_public_tool_contracts(environment)
        self.assertEqual([item["name"] for item in contracts], ["a","z"])
        self.assertEqual(set(contracts[0]), {"name","description","parameters"})


if __name__ == "__main__":
    unittest.main()
