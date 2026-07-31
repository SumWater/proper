from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "proper_v2"))

from timeout_capacity_v2 import (  # noqa: E402
    PUBLIC_TIMEOUT_CONTRACT,
    cpu_dry_run,
    load_config,
    prior_source_task_ids,
    summarize_records,
    synthetic_target,
)


class TimeoutCapacityV2Tests(unittest.TestCase):
    def test_all_prior_result_sources_are_excluded(self) -> None:
        excluded, counts = prior_source_task_ids(load_config())
        self.assertEqual(
            counts,
            {"argument_omission": 189, "transient_authorization": 175},
        )
        self.assertEqual(len(excluded), 364)

    def test_cpu_dry_run_reads_no_public_test_or_model_output(self) -> None:
        result = cpu_dry_run()
        self.assertFalse(result["model_loaded"])
        self.assertFalse(result["public_test_read"])
        self.assertTrue(result["synthetic_non_model_output"])
        self.assertTrue(result["decision"]["selection_changed"])
        self.assertEqual(
            result["decision"]["selected_experience_id"], "retry-memory"
        )

    def test_timeout_retry_safety_has_explicit_public_evidence(self) -> None:
        target = synthetic_target()
        self.assertEqual(target.retry_safety.status.value, "safe")
        self.assertIn(PUBLIC_TIMEOUT_CONTRACT, target.satisfied_facts)
        self.assertIn(PUBLIC_TIMEOUT_CONTRACT, target.retry_safety.evidence_codes)

    def test_capacity_summary_enforces_all_five_gates(self) -> None:
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
        summary = summarize_records(records, load_config())
        self.assertTrue(summary["future_protocol_preparation_authorized"])
        self.assertFalse(summary["gpu_run_authorized"])

    def test_capacity_summary_rejects_concentrated_changes(self) -> None:
        records = [
            {
                "selection_changed": index < 20,
                "selected_experience_id": "one-memory",
                "target_tool_name": f"tool-{index % 4}",
            }
            for index in range(50)
        ]
        summary = summarize_records(records, load_config())
        self.assertFalse(summary["future_protocol_preparation_authorized"])
        self.assertFalse(
            summary["capacity_checks"]["memory_concentration_limit_met"]
        )


if __name__ == "__main__":
    unittest.main()
