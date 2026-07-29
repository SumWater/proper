from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSIONED_TOP_LEVEL = {"configs", "docs", "experiments", "outputs", "schemas"}


def migrated_v1_path(relative: str) -> Path:
    """Resolve a path recorded before the non-byte-changing v1 directory move."""

    parts = Path(relative).parts
    if parts and parts[0] in VERSIONED_TOP_LEVEL:
        return ROOT / parts[0] / "proper_v1" / Path(*parts[1:])
    return ROOT / relative


class ManifestPortabilityTests(unittest.TestCase):
    def test_sha256sum_manifests_use_lf_only(self) -> None:
        for relative in (
            "configs/proper_v1/project_source.sha256",
            "configs/proper_v1/toolmisusebench_source.runtime.sha256",
        ):
            payload = (ROOT / relative).read_bytes()
            self.assertNotIn(b"\r", payload, relative)
            self.assertTrue(payload.endswith(b"\n"), relative)

    def test_project_manifest_uses_sha256sum_separator(self) -> None:
        manifest = ROOT / "configs" / "proper_v1" / "project_source.sha256"
        for line in manifest.read_text(encoding="utf-8").splitlines():
            expected, separator, relative = line.partition("  ")
            self.assertEqual(len(expected), 64)
            self.assertEqual(separator, "  ")
            self.assertTrue(migrated_v1_path(relative).is_file(), relative)


if __name__ == "__main__":
    unittest.main()
