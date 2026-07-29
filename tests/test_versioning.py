from __future__ import annotations

import unittest
from pathlib import Path

from tests.path_helpers import ROOT
from failure_memory.versioning import resolve_versioned_artifact


class VersionedArtifactPathTests(unittest.TestCase):
    def test_historical_v1_path_is_mapped_into_v1_namespace(self) -> None:
        value = resolve_versioned_artifact(ROOT, "configs/candidate_rules.yaml")
        self.assertEqual(value, ROOT / "configs" / "proper_v1" / "candidate_rules.yaml")

    def test_already_versioned_path_is_not_double_prefixed(self) -> None:
        value = resolve_versioned_artifact(
            ROOT, "outputs/proper_v1/confirmatory_gate_v1/results.json"
        )
        self.assertEqual(
            value,
            ROOT / "outputs" / "proper_v1" / "confirmatory_gate_v1" / "results.json",
        )

    def test_work_path_remains_unversioned(self) -> None:
        value = resolve_versioned_artifact(ROOT, Path("work/memory_bank_prepared.json"))
        self.assertEqual(value, ROOT / "work" / "memory_bank_prepared.json")


if __name__ == "__main__":
    unittest.main()
