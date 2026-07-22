from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from failure_memory.candidate_selector import PolicyClass  # noqa: E402
from failure_memory.transient_authz_gate import (  # noqa: E402
    TransientAuthzCandidate,
    select_transient_authz_memory,
)


def observation(code: str = "authz_denied") -> dict:
    failed = {
        "tool_name": "read_file",
        "args": {"path": "/visible/example"},
        "error": {"code": code, "message": "Failure", "details": {}},
        "output": None,
    }
    return {
        "last_error": failed["error"],
        "tool_schemas": [
            {
                "name": "read_file",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            }
        ],
        "transcript": [failed],
    }


def candidate(name: str, rank: int, policy: PolicyClass, tool: str = "read_file") -> Any:
    return TransientAuthzCandidate(name, rank, policy, tool)


class TransientAuthzGateTests(unittest.TestCase):
    def test_rank1_retry_is_preserved_exactly(self) -> None:
        decision = select_transient_authz_memory(
            observation(),
            [
                candidate("rank1", 1, PolicyClass.RETRY, "other_tool"),
                candidate("same-tool", 2, PolicyClass.RETRY),
            ],
        )
        self.assertEqual(decision.selected_experience_id, "rank1")
        self.assertFalse(decision.selection_changed)

    def test_nonretry_rank1_is_replaced_with_retry(self) -> None:
        decision = select_transient_authz_memory(
            observation(),
            [
                candidate("stop", 1, PolicyClass.STOP),
                candidate("retry", 2, PolicyClass.RETRY),
            ],
        )
        self.assertEqual(decision.selected_experience_id, "retry")
        self.assertTrue(decision.selection_changed)

    def test_same_tool_retry_is_preferred(self) -> None:
        decision = select_transient_authz_memory(
            observation(),
            [
                candidate("stop", 1, PolicyClass.STOP),
                candidate("other", 2, PolicyClass.RETRY, "search_docs"),
                candidate("same", 5, PolicyClass.RETRY),
            ],
        )
        self.assertEqual(decision.selected_experience_id, "same")

    def test_non_authz_observation_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "first authz_denied"):
            select_transient_authz_memory(
                observation("timeout"), [candidate("retry", 1, PolicyClass.RETRY)]
            )

    def test_missing_retry_memory_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "no retry memory"):
            select_transient_authz_memory(
                observation(), [candidate("stop", 1, PolicyClass.STOP)]
            )

    def test_hidden_recoverability_is_rejected(self) -> None:
        value = observation()
        value["recoverability"] = "transient"
        with self.assertRaisesRegex(ValueError, "forbidden selector input"):
            select_transient_authz_memory(
                value, [candidate("retry", 1, PolicyClass.RETRY)]
            )


if __name__ == "__main__":
    unittest.main()
