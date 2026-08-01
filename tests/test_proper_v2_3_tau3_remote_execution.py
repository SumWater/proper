from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "proper_v2_3" / "tau3_remote_execution_v2_3.yaml"
REQUIREMENTS = ROOT / "configs" / "proper_v2_3" / "requirements_tau3_remote_v2_3.txt"
BOOTSTRAP = ROOT / "experiments" / "proper_v2_3" / "run_tau3_remote_v2_3.py"
RUNNER = ROOT / "experiments" / "proper_v2_3" / "tau3_remote_execution_v2_3.py"
SCHEMA = ROOT / "schemas" / "proper_v2_3" / "tau3_remote_execution.schema.json"


class Tau3RemoteExecutionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG.read_text(encoding="utf-8"))

    def test_local_self_test_is_explicitly_noncanonical(self) -> None:
        local = self.config["local_self_test_is_not_formal_evidence"]
        self.assertFalse(local["canonical_remote_result"])
        self.assertEqual(local["commit"], "42de557")
        self.assertNotEqual(local["branch_result"], self.config["remote_outputs"]["root"])

    def test_remote_output_is_separate_and_never_overwritten(self) -> None:
        outputs = self.config["remote_outputs"]
        self.assertEqual(outputs["root"], "outputs/proper_v2_3/tau3_branch_screen_remote")
        self.assertTrue(outputs["never_overwrite_existing_run"])

    def test_runtime_is_cpu_only_and_authorizes_no_model_claim(self) -> None:
        guards = self.config["runtime_guards"]
        self.assertEqual(self.config["python"]["allowed_minors"], [11, 12])
        self.assertTrue(guards["cpu_only"])
        self.assertEqual(guards["cuda_visible_devices"], "-1")
        self.assertFalse(guards["model_loading_authorized"])
        self.assertFalse(guards["gpu_use_authorized"])
        self.assertFalse(guards["confirmatory_claim_authorized"])

    def test_exact_top_level_requirements_cover_tau_and_full_regression(self) -> None:
        lines = [line.strip() for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines()
                 if line.strip() and not line.startswith("#")]
        self.assertTrue(all("==" in line for line in lines))
        names = {line.split("==", 1)[0].lower() for line in lines}
        self.assertTrue({"pydantic", "loguru", "jsonschema", "pyyaml", "scikit-learn"}.issubset(names))

    def test_cross_platform_entry_requires_revision_and_sets_remote_role(self) -> None:
        source = BOOTSTRAP.read_text(encoding="utf-8")
        self.assertIn('parser.add_argument("--expected-project-revision", required=True)', source)
        self.assertIn("PROPER_V2_3_EXECUTION_ROLE", source)
        self.assertIn("CUDA_VISIBLE_DEVICES", source)
        self.assertIn("tau3_remote_execution_v2_3.py", source)
        self.assertIn('if os.name == "nt"', source)

    def test_runner_fails_closed_on_revision_or_dirty_worktree(self) -> None:
        source = RUNNER.read_text(encoding="utf-8")
        self.assertIn("project revision mismatch", source)
        self.assertIn("tracked project worktree must be clean", source)
        self.assertIn("mkdir(parents=True, exist_ok=False)", source)
        self.assertIn("stop_and_preserve_remote_negative_result", CONFIG.read_text(encoding="utf-8"))

    def test_remote_envelope_schema_is_closed_and_keeps_heldout_zero(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.assertFalse(schema["additionalProperties"])
        boundary = schema["properties"]["boundary"]["properties"]
        self.assertEqual(boundary["new_heldout_target_capacity"]["const"], 0)
        self.assertFalse(boundary["development_model_run_authorized"]["const"])
        self.assertFalse(boundary["confirmatory_run_authorized"]["const"])


if __name__ == "__main__":
    unittest.main()
