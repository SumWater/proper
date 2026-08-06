"""Aggregate-only in-memory inventory for an AppWorld-style encrypted bundle."""

from __future__ import annotations

import hashlib
import io
import json
import stat
import zipfile
from pathlib import PurePosixPath
from typing import Any, Mapping


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _decrypt(encrypted: bytes, *, password: str, salt: bytes, iterations: int) -> bytes:
    if len(encrypted) <= 16:
        raise ValueError("encrypted bundle is too short")
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    try:
        from cryptography.hazmat.decrepit.ciphers import modes
    except ImportError:  # cryptography < 43
        from cryptography.hazmat.primitives.ciphers import modes

    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iterations).derive(password.encode("utf-8"))
    decryptor = Cipher(algorithms.AES(key), modes.CFB(encrypted[:16])).decryptor()
    return decryptor.update(encrypted[16:]) + decryptor.finalize()


def _safe_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if not name or "\\" in name or path.is_absolute() or ".." in path.parts:
        raise ValueError("unsafe protected member path")
    return path


def inventory_encrypted_bundle(
    encrypted: bytes,
    *,
    expected_encrypted_bytes: int,
    expected_encrypted_sha256: str,
    password: str,
    salt: bytes,
    iterations: int,
    limits: Mapping[str, int],
) -> dict[str, Any]:
    """Decrypt only in memory and return no protected plaintext identifiers."""

    if len(encrypted) != expected_encrypted_bytes:
        raise ValueError("encrypted bundle byte size mismatch")
    encrypted_sha256 = hashlib.sha256(encrypted).hexdigest()
    if encrypted_sha256 != expected_encrypted_sha256:
        raise ValueError("encrypted bundle SHA-256 mismatch")
    decrypted = _decrypt(encrypted, password=password, salt=salt, iterations=iterations)
    decrypted_zip_sha256 = hashlib.sha256(decrypted).hexdigest()
    records: list[dict[str, Any]] = []
    extension_counts: dict[str, int] = {}
    names: set[str] = set()
    total_uncompressed = 0
    try:
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
                content = archive.read(info)
                suffix = member.suffix.lower() or "<none>"
                extension_counts[suffix] = extension_counts.get(suffix, 0) + 1
                records.append({
                    "path_sha256": hashlib.sha256(member.as_posix().encode("utf-8")).hexdigest(),
                    "content_sha256": hashlib.sha256(content).hexdigest(),
                    "uncompressed_bytes": info.file_size,
                    "compressed_bytes": info.compress_size,
                })
    except zipfile.BadZipFile as exc:
        raise ValueError("decrypted bundle is not a valid ZIP archive") from exc
    records.sort(key=lambda item: item["path_sha256"])
    return {
        "encrypted_bytes": len(encrypted),
        "encrypted_sha256": encrypted_sha256,
        "decrypted_zip_sha256": decrypted_zip_sha256,
        "member_count": len(records),
        "total_uncompressed_bytes": total_uncompressed,
        "extension_counts": dict(sorted(extension_counts.items())),
        "hashed_members": records,
        "hashed_member_manifest_sha256": canonical_sha256(records),
        "decrypted_in_memory_only": True,
        "source_extracted": False,
        "protected_plaintext_persisted": False,
    }
