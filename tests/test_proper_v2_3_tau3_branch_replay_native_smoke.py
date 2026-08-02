from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "experiments/proper_v2_3/run_tau3_branch_replay_native_smoke_remote_v2_3.py"


class Tau3BranchReplayNativeSmokeTests(unittest.TestCase):
    def test_remote_entry_is_syntax_valid_and_has_no_model_runner_import(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        ast.parse(source)
        self.assertNotIn("transformers", source)
        self.assertNotIn("torch", source)
        self.assertNotIn("evaluation_criteria", source)
        self.assertNotIn("get_tasks(", source)

    def test_config_freezes_cpu_only_boundary(self) -> None:
        config = json.loads((ROOT / "configs/proper_v2_3/tau3_branch_replay_native_smoke_v2_3.json").read_text(encoding="utf-8"))
        self.assertFalse(config["gates"]["authorize_model_runner"])
        self.assertFalse(config["gates"]["authorize_model_run"])
        self.assertFalse(config["gates"]["authorize_gpu"])
        self.assertEqual(config["fixture"]["expected_native_execution_count"], 1)
        self.assertEqual(config["source"]["allowed_python_minors"], [11, 12])
        self.assertFalse(config["protocol_v2_correction"]["native_action_executed_in_failed_attempt"])
        self.assertFalse(config["protocol_v2_correction"]["method_or_evaluation_changed"])

    def test_output_schema_is_closed_and_forbids_model_claims(self) -> None:
        schema = json.loads((ROOT / "schemas/proper_v2_3/tau3_branch_replay_native_smoke.schema.json").read_text(encoding="utf-8"))
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["properties"]["model_loaded"], {"const": False})
        self.assertEqual(schema["properties"]["gpu_used"], {"const": False})


if __name__ == "__main__":
    unittest.main()
