from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "proper_v1"))

from gate_dataset import (  # noqa: E402
    load_config,
    load_exclusions,
    prepare_payload,
    resolve_root_path,
)


class ConfirmatoryPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_config()
        cls.payload, _ = prepare_payload()

    def test_pilot_source_memory_source_and_target_sets_are_disjoint(self) -> None:
        excluded, _ = load_exclusions(resolve_root_path(self.config["pilot_exclusions"]))
        sources = {item["source_task_id"] for item in self.payload["memory_sources"]}
        targets = {item["source_task_id"] for item in self.payload["records"]}
        self.assertFalse(excluded & sources)
        self.assertFalse(excluded & targets)
        self.assertFalse(sources & targets)

    def test_capacity_gate_uses_frozen_minimum(self) -> None:
        screening = self.payload["screening"]
        self.assertEqual(screening["minimum_required_pair_count"], 50)
        self.assertEqual(
            screening["gpu_run_authorized_by_capacity"],
            screening["matched_confirmatory_pair_count"] >= 50,
        )

    def test_every_selected_pair_has_four_clean_full_prompts(self) -> None:
        expected = set(self.config["conditions"]["fixed_order"])
        forbidden = self.config["agent_boundary"]["forbidden_agent_fields"]
        for pair in self.payload["selected_pairs"]:
            self.assertEqual(set(pair["prompts"]), expected)
            for prompt in pair["prompts"].values():
                self.assertTrue(prompt.startswith("Choose the single next recovery decision"))
                self.assertFalse(any(field in prompt.lower() for field in forbidden))


if __name__ == "__main__":
    unittest.main()
