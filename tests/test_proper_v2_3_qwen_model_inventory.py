from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.failure_memory.proper_v2.v2_3.model_inventory import (
    file_sha256,
    inventory_regular_files,
)
from experiments.proper_v2_3 import run_qwen_model_inventory_remote_v2_3 as remote_runner


class QwenModelInventoryTests(unittest.TestCase):
    def test_inventory_is_sorted_complete_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw).resolve()
            (root / "nested").mkdir()
            (root / "z.bin").write_bytes(b"weights")
            (root / "nested/a.json").write_bytes(b"{}")
            first = inventory_regular_files(root, chunk_bytes=3)
            second = inventory_regular_files(root, chunk_bytes=8)
            self.assertEqual([item["relative_path"] for item in first["files"]], ["nested/a.json", "z.bin"])
            self.assertEqual(first["manifest_sha256"], second["manifest_sha256"])
            self.assertEqual(first["total_bytes"], 9)

    def test_content_change_changes_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw).resolve()
            target = root / "model.safetensors"
            target.write_bytes(b"one")
            before = inventory_regular_files(root, chunk_bytes=2)["manifest_sha256"]
            target.write_bytes(b"two")
            after = inventory_regular_files(root, chunk_bytes=2)["manifest_sha256"]
            self.assertNotEqual(before, after)

    def test_streaming_file_hash_matches_reference(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "data"
            target.write_bytes(b"abcdefgh")
            self.assertEqual(file_sha256(target, chunk_bytes=3), hashlib.sha256(b"abcdefgh").hexdigest())

    def test_relative_and_empty_roots_stop_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "absolute"):
            inventory_regular_files(Path("relative"), chunk_bytes=1)
        with tempfile.TemporaryDirectory() as raw, self.assertRaisesRegex(ValueError, "no regular files"):
            inventory_regular_files(Path(raw).resolve(), chunk_bytes=1)

    def test_symlink_stops_closed_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw).resolve()
            target = root / "target"
            target.write_bytes(b"x")
            link = root / "link"
            try:
                link.symlink_to(target)
            except OSError:
                self.skipTest("symlink creation is unavailable")
            with self.assertRaisesRegex(ValueError, "symbolic links"):
                inventory_regular_files(root, chunk_bytes=1)

    def test_remote_result_has_exact_closed_schema_fields(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            temporary = Path(raw).resolve()
            model_root = temporary / "model"
            model_root.mkdir()
            (model_root / "config.json").write_bytes(b"{}")
            config = json.loads((ROOT / "configs/proper_v2_3/qwen_model_inventory_v2_3.json").read_text(encoding="utf-8"))
            config["model_root"] = str(model_root)
            config_path = temporary / "inventory_config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            revision = "a" * 40
            original_config, original_git = remote_runner.CONFIG, remote_runner._git
            try:
                remote_runner.CONFIG = config_path
                remote_runner._git = lambda *args: revision if args == ("rev-parse", "HEAD") else ""
                result = remote_runner.run(revision)
            finally:
                remote_runner.CONFIG, remote_runner._git = original_config, original_git
            schema = json.loads((ROOT / "schemas/proper_v2_3/qwen_model_inventory.schema.json").read_text(encoding="utf-8"))
            self.assertTrue(result["passed"])
            self.assertEqual(result["file_count"], 1)
            self.assertEqual(set(result), set(schema["required"]))
            self.assertFalse(result["model_loaded"])
            self.assertFalse(result["gpu_used"])


if __name__ == "__main__":
    unittest.main()
