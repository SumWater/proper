"""Dependency-free, read-only content inventory for a local model directory."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def file_sha256(path: Path, *, chunk_bytes: int) -> str:
    if chunk_bytes <= 0:
        raise ValueError("chunk_bytes must be positive")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_bytes):
            digest.update(chunk)
    return digest.hexdigest()


def inventory_regular_files(model_root: Path, *, chunk_bytes: int) -> dict[str, Any]:
    if not model_root.is_absolute():
        raise ValueError("model_root must be absolute")
    root = model_root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("model_root must resolve to a directory")

    files: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise ValueError(f"symbolic links are forbidden: {relative}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError(f"non-regular model entry is forbidden: {relative}")
        size = path.stat().st_size
        files.append(
            {
                "relative_path": relative,
                "size_bytes": size,
                "sha256": file_sha256(path, chunk_bytes=chunk_bytes),
            }
        )
    if not files:
        raise ValueError("model directory contains no regular files")
    return {
        "files": files,
        "file_count": len(files),
        "total_bytes": sum(item["size_bytes"] for item in files),
        "manifest_sha256": canonical_sha256(files),
    }
