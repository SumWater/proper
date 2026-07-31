from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from failure_memory.proper_v2.boundary import (
    assert_observable_payload,
    observable_failure_from_mapping,
)


def observable_payload() -> dict:
    return {
        "schema_version": 1,
        "instruction": "Search for the requested document.",
        "failed_action": {"tool_name": "search_docs", "arguments": {}},
        "error_code": "missing_required_arg",
        "evidence_codes": ["missing_required_arg", "missing:query"],
        "failed_argument_paths": [],
        "missing_fields": ["query"],
        "public_schema_fields": ["query"],
        "public_required_fields": ["query"],
        "available_tools": ["get_doc", "search_docs"],
        "available_capabilities": ["document_retrieval"],
        "satisfied_facts": [],
        "violated_facts": [],
        "repeated_same_call_count": 1,
        "retry_safety": {"status": "unknown", "evidence_codes": []},
    }


class ProperV2BoundaryTests(unittest.TestCase):
    def test_hidden_evaluator_field_is_rejected_recursively(self) -> None:
        payload = observable_payload()
        payload["failed_action"]["arguments"]["nested"] = {
            "recoverability": "transient"
        }
        with self.assertRaisesRegex(ValueError, "forbidden PROPER v2 input"):
            observable_failure_from_mapping(payload)

    def test_injection_only_metadata_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "original_error_code"):
            assert_observable_payload(
                {"error": {"details": {"original_error_code": "permission_error"}}}
            )

    def test_known_retry_safety_requires_public_evidence(self) -> None:
        payload = observable_payload()
        payload["retry_safety"] = {"status": "safe", "evidence_codes": []}
        with self.assertRaisesRegex(ValueError, "requires public evidence"):
            observable_failure_from_mapping(payload)

    def test_public_fact_cannot_be_both_satisfied_and_violated(self) -> None:
        payload = observable_payload()
        payload["satisfied_facts"] = ["authenticated"]
        payload["violated_facts"] = ["authenticated"]
        with self.assertRaisesRegex(ValueError, "both satisfied and violated"):
            observable_failure_from_mapping(payload)


if __name__ == "__main__":
    unittest.main()
