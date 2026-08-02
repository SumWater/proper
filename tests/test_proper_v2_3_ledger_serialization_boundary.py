from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from failure_memory.proper_v2.v2_3 import execution_ledger_from_mapping


class ProperV23LedgerSerializationBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        result = json.loads(
            (
                ROOT / "outputs/proper_v2_3/tau3_branch_screen/branch_screen.json"
            ).read_text(encoding="utf-8")
        )
        cls.mapping = result["pairs"][0]["ledger"]

    def test_frozen_ledger_round_trips(self) -> None:
        ledger = execution_ledger_from_mapping(self.mapping)
        self.assertEqual(ledger.to_mapping(), self.mapping)

    def test_tampered_action_identity_is_rejected(self) -> None:
        tampered = copy.deepcopy(self.mapping)
        tampered["entries"][0]["action"]["normalized_identity"] = "0" * 64
        with self.assertRaises(ValueError):
            execution_ledger_from_mapping(tampered)

    def test_non_boolean_decision_allowed_is_rejected(self) -> None:
        tampered = copy.deepcopy(self.mapping)
        tampered["entries"][0]["decision_allowed"] = "true"
        with self.assertRaises(ValueError):
            execution_ledger_from_mapping(tampered)

    def test_hidden_benchmark_field_is_rejected(self) -> None:
        tampered = copy.deepcopy(self.mapping)
        tampered["entries"][0]["gold_action"] = "hidden"
        with self.assertRaises(ValueError):
            execution_ledger_from_mapping(tampered)


if __name__ == "__main__":
    unittest.main()
