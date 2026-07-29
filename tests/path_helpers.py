from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from failure_memory.versioning import resolve_versioned_artifact  # noqa: E402


def v1_path(value: str | Path) -> Path:
    return resolve_versioned_artifact(ROOT, value, version="proper_v1")
