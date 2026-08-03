from __future__ import annotations

import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path


from src.failure_memory.proper_v2.v2_3.offline_wheel_inventory import inventory_wheel


LIMITS = {
    "maximum_member_count": 20,
    "maximum_member_uncompressed_bytes": 4096,
    "maximum_total_uncompressed_bytes": 16384,
    "maximum_compression_ratio": 100,
}


def make_wheel(root: Path, *, unsafe: bool = False, include_bundle: bool = True, version: str = "1.2.3") -> Path:
    path = root / "sample-1.2.3-py3-none-any.whl"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("sample/__init__.py", "")
        if include_bundle:
            archive.writestr("sample/protected.bundle", b"encrypted fixture")
        archive.writestr("sample-1.2.3.dist-info/METADATA", f"Name: sample\nVersion: {version}\n")
        archive.writestr("sample-1.2.3.dist-info/WHEEL", "Wheel-Version: 1.0\n")
        archive.writestr("sample-1.2.3.dist-info/RECORD", "")
        if unsafe:
            archive.writestr("../escape.txt", "forbidden")
    return path


def inspect(path: Path, **overrides: object) -> dict:
    arguments = {
        "expected_filename": path.name,
        "expected_size_bytes": path.stat().st_size,
        "expected_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "expected_distribution": "sample",
        "expected_version": "1.2.3",
        "limits": LIMITS,
    }
    arguments.update(overrides)
    return inventory_wheel(path, **arguments)


class AppWorldOfflineWheelInventoryTests(unittest.TestCase):
    def test_safe_exact_wheel_is_inventoried_without_extraction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = inspect(make_wheel(Path(directory)))
        self.assertEqual(result["bundle_count"], 1)
        self.assertFalse(result["wheel_extracted"])
        self.assertFalse(result["protected_bundle_opened"])
        self.assertEqual(result["members"], sorted(result["members"], key=lambda item: item["relative_path"]))

    def test_hash_size_and_filename_mismatches_stop(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = make_wheel(Path(directory))
            cases = (
                {"expected_filename": "other.whl"},
                {"expected_size_bytes": path.stat().st_size + 1},
                {"expected_sha256": "0" * 64},
            )
            for values in cases:
                with self.subTest(values=values), self.assertRaises(ValueError):
                    inspect(path, **values)

    def test_unsafe_member_path_stops_before_extraction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "unsafe wheel member"):
                inspect(make_wheel(Path(directory), unsafe=True))

    def test_missing_encrypted_bundle_stops(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "encrypted .bundle"):
                inspect(make_wheel(Path(directory), include_bundle=False))

    def test_distribution_and_version_metadata_are_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = make_wheel(Path(directory))
            with self.assertRaisesRegex(ValueError, "distribution metadata"):
                inspect(path, expected_distribution="other")
            with self.assertRaisesRegex(ValueError, "version metadata"):
                inspect(path, expected_version="9.9.9")


if __name__ == "__main__":
    unittest.main()
