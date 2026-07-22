from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ManifestPortabilityTests(unittest.TestCase):
    def test_sha256sum_manifests_use_lf_only(self) -> None:
        for relative in (
            "configs/project_source.sha256",
            "configs/toolmisusebench_source.runtime.sha256",
        ):
            payload = (ROOT / relative).read_bytes()
            self.assertNotIn(b"\r", payload, relative)
            self.assertTrue(payload.endswith(b"\n"), relative)

    def test_project_manifest_uses_sha256sum_separator(self) -> None:
        manifest = ROOT / "configs" / "project_source.sha256"
        for line in manifest.read_text(encoding="utf-8").splitlines():
            expected, separator, relative = line.partition("  ")
            self.assertEqual(len(expected), 64)
            self.assertEqual(separator, "  ")
            self.assertTrue((ROOT / relative).is_file(), relative)


if __name__ == "__main__":
    unittest.main()
