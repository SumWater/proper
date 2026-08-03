"""Read-only inventory for a wheel without importing or extracting it."""

from __future__ import annotations

import hashlib
import json
import stat
import zipfile
from email.parser import Parser
from pathlib import Path, PurePosixPath
from typing import Any, Mapping


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path: Path, chunk_bytes: int = 1024 * 1024) -> str:
    if chunk_bytes <= 0:
        raise ValueError("chunk_bytes must be positive")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_bytes):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_member(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if not name or "\\" in name or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe wheel member path: {name!r}")
    return path


def inventory_wheel(
    wheel_path: Path,
    *,
    expected_filename: str,
    expected_size_bytes: int,
    expected_sha256: str,
    expected_distribution: str,
    expected_version: str,
    limits: Mapping[str, int],
) -> dict[str, Any]:
    """Inspect exact wheel bytes and ZIP members without extraction."""

    path = wheel_path.resolve(strict=True)
    if not path.is_file() or path.is_symlink():
        raise ValueError("wheel must be one regular non-symlink file")
    if path.name != expected_filename:
        raise ValueError("wheel filename does not match frozen release")
    observed_size = path.stat().st_size
    if observed_size != expected_size_bytes:
        raise ValueError("wheel byte size does not match frozen release")
    observed_sha256 = file_sha256(path)
    if observed_sha256 != expected_sha256:
        raise ValueError("wheel SHA-256 does not match frozen release")

    records: list[dict[str, Any]] = []
    metadata_text: str | None = None
    names: set[str] = set()
    total_uncompressed = 0
    with zipfile.ZipFile(path, "r") as archive:
        infos = archive.infolist()
        if not infos or len(infos) > limits["maximum_member_count"]:
            raise ValueError("wheel member count is outside the frozen limit")
        for info in infos:
            member = _safe_member(info.filename)
            if info.filename in names:
                raise ValueError(f"duplicate wheel member: {info.filename}")
            names.add(info.filename)
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise ValueError(f"symbolic-link wheel member is forbidden: {info.filename}")
            if info.is_dir():
                continue
            if info.file_size > limits["maximum_member_uncompressed_bytes"]:
                raise ValueError(f"wheel member exceeds size limit: {info.filename}")
            total_uncompressed += info.file_size
            if total_uncompressed > limits["maximum_total_uncompressed_bytes"]:
                raise ValueError("wheel exceeds total uncompressed size limit")
            if info.compress_size == 0 and info.file_size > 0:
                raise ValueError(f"invalid compressed size: {info.filename}")
            if info.compress_size and info.file_size / info.compress_size > limits["maximum_compression_ratio"]:
                raise ValueError(f"wheel member exceeds compression-ratio limit: {info.filename}")
            content = archive.read(info)
            records.append({
                "relative_path": member.as_posix(),
                "compressed_bytes": info.compress_size,
                "uncompressed_bytes": info.file_size,
                "sha256": hashlib.sha256(content).hexdigest(),
            })
            if member.name == "METADATA" and ".dist-info" in member.parent.name:
                if metadata_text is not None:
                    raise ValueError("wheel contains multiple METADATA files")
                metadata_text = content.decode("utf-8")

    if metadata_text is None:
        raise ValueError("wheel METADATA is missing")
    metadata = Parser().parsestr(metadata_text)
    if metadata.get("Name", "").lower().replace("_", "-") != expected_distribution.lower().replace("_", "-"):
        raise ValueError("wheel distribution metadata does not match")
    if metadata.get("Version") != expected_version:
        raise ValueError("wheel version metadata does not match")
    records.sort(key=lambda item: item["relative_path"])
    bundle_paths = [item["relative_path"] for item in records if item["relative_path"].endswith(".bundle")]
    if not bundle_paths:
        raise ValueError("wheel contains no encrypted .bundle member")
    required_dist_info = {"METADATA", "WHEEL", "RECORD"}
    observed_dist_info = {
        PurePosixPath(item["relative_path"]).name
        for item in records
        if ".dist-info" in PurePosixPath(item["relative_path"]).parent.name
    }
    if not required_dist_info <= observed_dist_info:
        raise ValueError("wheel is missing required dist-info members")
    return {
        "wheel_filename": path.name,
        "wheel_size_bytes": observed_size,
        "wheel_sha256": observed_sha256,
        "distribution": expected_distribution,
        "version": expected_version,
        "member_count": len(records),
        "total_uncompressed_bytes": sum(item["uncompressed_bytes"] for item in records),
        "bundle_count": len(bundle_paths),
        "bundle_paths": bundle_paths,
        "members": records,
        "member_manifest_sha256": _canonical_sha256(records),
        "wheel_extracted": False,
        "protected_bundle_opened": False,
    }
