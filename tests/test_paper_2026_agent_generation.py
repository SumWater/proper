from __future__ import annotations

import json
import unittest
from pathlib import Path

import yaml

from experiments.paper_2026 import build_agent_prompt_cache as cache_builder
from experiments.paper_2026 import run_agent_generation as generation


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "paper_2026" / "agent_generation_v1_0.yaml"


class Paper2026AgentGenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))

    def test_generation_config_and_all_inputs_are_hash_frozen(self) -> None:
        verified = generation.verify_frozen(self.config)
        self.assertEqual(set(verified), set(self.config["inputs"]))
        self.assertTrue(self.config["boundary"]["formal_agent_generation_authorized"])

    def test_frozen_unique_prompt_call_counts_reconstruct(self) -> None:
        qwen, _ = generation.load_plan(self.config, "qwen3_8b")
        mistral, _ = generation.load_plan(self.config, "mistral_7b_instruct_v0_3")
        self.assertEqual(len(qwen), 708)
        self.assertEqual(len(mistral), 1611)
        self.assertTrue(
            {item["prompt_sha256"] for item in qwen}.issubset(
                {item["prompt_sha256"] for item in mistral}
            )
        )

    def test_cache_join_is_model_output_only_and_exact(self) -> None:
        join = json.loads(
            (ROOT / "outputs/paper_2026/agent_prompt_cache/cache_join.json").read_text(
                encoding="utf-8"
            )
        )
        counts = {"reusable_exact_identity": 0, "miss": 0}
        for record in join["records"]:
            counts[record["qwen_cache_status"]] += 1
            if record["qwen_cache_status"] == "reusable_exact_identity":
                self.assertTrue(record["historical_provenance"])
                self.assertTrue(
                    all(
                        item["prefix_sha256"] == record["prefix_sha256"]
                        for item in record["historical_provenance"]
                    )
                )
        self.assertEqual(counts, {"reusable_exact_identity": 903, "miss": 708})

    def test_historical_cache_core_excludes_instance_specific_outcomes(self) -> None:
        condition = {
            "prompt": "p",
            "prompt_sha256": "h",
            "prefix_hash": "x",
            "model_output": "{}",
            "model_output_sha256": "m",
            "decision": {"kind": "stop", "reason_code": "x"},
            "parse_valid": True,
            "parse_error": None,
            "outcome": {"recovery_validity": True},
            "trace_sha256": "instance-specific",
        }
        core = cache_builder.historical_core(condition)
        self.assertNotIn("outcome", core)
        self.assertNotIn("trace_sha256", core)
        self.assertIn("model_output", core)


if __name__ == "__main__":
    unittest.main()
