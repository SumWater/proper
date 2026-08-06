"""Decrypt a protected bundle and produce only a hash-only static API inventory."""

from __future__ import annotations

import hashlib
import io
import stat
import zipfile
from typing import Any, Mapping

from .encrypted_bundle_inventory import _decrypt, _safe_path
from .static_api_inventory import inventory_static_api_sources


def inventory_encrypted_static_api_bundle(
    encrypted: bytes,
    *,
    expected_encrypted_bytes: int,
    expected_encrypted_sha256: str,
    password: str,
    salt: bytes,
    iterations: int,
    limits: Mapping[str, int],
) -> dict[str, Any]:
    if len(encrypted) != expected_encrypted_bytes:
        raise ValueError("encrypted bundle byte size mismatch")
    encrypted_sha256 = hashlib.sha256(encrypted).hexdigest()
    if encrypted_sha256 != expected_encrypted_sha256:
        raise ValueError("encrypted bundle SHA-256 mismatch")
    decrypted = _decrypt(encrypted, password=password, salt=salt, iterations=iterations)
    decrypted_zip_sha256 = hashlib.sha256(decrypted).hexdigest()
    sources: dict[str, bytes] = {}
    names: set[str] = set()
    total_uncompressed = 0
    with zipfile.ZipFile(io.BytesIO(decrypted), "r") as archive:
        infos = archive.infolist()
        if not infos or len(infos) > limits["maximum_member_count"]:
            raise ValueError("protected member count is outside limit")
        for info in infos:
            member = _safe_path(info.filename)
            if info.filename in names:
                raise ValueError("duplicate protected member")
            names.add(info.filename)
            if stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError("protected symbolic-link member is forbidden")
            if info.is_dir():
                continue
            if info.file_size > limits["maximum_member_uncompressed_bytes"]:
                raise ValueError("protected member exceeds size limit")
            total_uncompressed += info.file_size
            if total_uncompressed > limits["maximum_total_uncompressed_bytes"]:
                raise ValueError("protected archive exceeds total size limit")
            if info.compress_size == 0 and info.file_size > 0:
                raise ValueError("invalid protected member compressed size")
            if info.compress_size and info.file_size / info.compress_size > limits["maximum_compression_ratio"]:
                raise ValueError("protected member exceeds compression-ratio limit")
            if member.suffix.lower() in {".py", ".pyi"}:
                sources[member.as_posix()] = archive.read(info)
    inventory = inventory_static_api_sources(sources)
    return {
        "encrypted_bytes": len(encrypted),
        "encrypted_sha256": encrypted_sha256,
        "decrypted_zip_sha256": decrypted_zip_sha256,
        "archive_member_count": len(names),
        "archive_total_uncompressed_bytes": total_uncompressed,
        "static_api_inventory": inventory,
        "decrypted_in_memory_only": True,
        "protected_plaintext_persisted": False,
        "source_extracted": False,
        "module_imported": False,
    }
