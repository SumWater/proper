from __future__ import annotations

import sys
import unittest
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from transient_authz_capacity_v1 import (  # noqa: E402
    cpu_dry_run,
    load_config,
    prior_source_task_ids,
    summarize_records,
)


class TransientAuthzCapacityV1Tests(unittest.TestCase):
    def test_frozen_capacity_sources_match_lock(self) -> None:
        lock = json.loads(
            (ROOT / "configs" / "transient_authz_capacity_v1.lock.json").read_text(
                encoding="utf-8"
            )
        )
        for key in ("config", "runner", "selector", "output_schema", "protocol"):
            item = lock[key]
            actual = hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest()
            self.assertEqual(actual, item["sha256"], key)
        self.assertFalse(lock["model_outputs_generated"])
        self.assertFalse(lock["gpu_run_authorized"])

    def test_prior_argument_omission_sources_are_frozen_exclusions(self) -> None:
        config = load_config()
        self.assertEqual(len(prior_source_task_ids(config)), 189)

    def test_capacity_summary_enforces_diversity_and_concentration(self) -> None:
        config = load_config()
        records = []
        for index in range(50):
            changed = index < 20
            records.append(
                {
                    "selection_changed": changed,
                    "selected_experience_id": f"memory-{index % 4}",
                    "target_tool_name": f"tool-{index % 4}",
                }
            )
        summary = summarize_records(records, config)
        self.assertTrue(summary["future_protocol_preparation_authorized"])
        self.assertFalse(summary["gpu_run_authorized"])

    def test_capacity_summary_rejects_single_memory_concentration(self) -> None:
        config = load_config()
        records = [
            {
                "selection_changed": index < 20,
                "selected_experience_id": "one-memory",
                "target_tool_name": f"tool-{index % 4}",
            }
            for index in range(50)
        ]
        summary = summarize_records(records, config)
        self.assertFalse(summary["future_protocol_preparation_authorized"])
        self.assertFalse(
            summary["capacity_checks"]["memory_concentration_limit_met"]
        )

    def test_cpu_dry_run_does_not_read_public_test_or_load_model(self) -> None:
        result = cpu_dry_run()
        self.assertFalse(result["model_loaded"])
        self.assertFalse(result["public_test_read"])
        self.assertTrue(result["decision"]["selection_changed"])


if __name__ == "__main__":
    unittest.main()
