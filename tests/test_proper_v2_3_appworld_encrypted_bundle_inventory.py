from __future__ import annotations

import hashlib
import io
import secrets
import stat
import unittest
import zipfile


from src.failure_memory.proper_v2.v2_3.encrypted_bundle_inventory import inventory_encrypted_bundle


PASSWORD = "synthetic-password"
SALT = b"synthetic-salt"
LIMITS = {
    "maximum_member_count": 20,
    "maximum_member_uncompressed_bytes": 4096,
    "maximum_total_uncompressed_bytes": 16384,
    "maximum_compression_ratio": 100,
}


def encrypted_fixture(*, unsafe: bool = False, duplicate: bool = False, symlink: bool = False) -> bytes:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    try:
        from cryptography.hazmat.decrepit.ciphers import modes
    except ImportError:
        from cryptography.hazmat.primitives.ciphers import modes

    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("apps/example/api.py", "def read_item(): return 1\n")
        archive.writestr("apps/example/models.py", "class Item: pass\n")
        if unsafe:
            archive.writestr("../escape.py", "bad")
        if duplicate:
            archive.writestr("apps/example/api.py", "duplicate")
        if symlink:
            info = zipfile.ZipInfo("apps/example/link.py")
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, "target")
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=SALT, iterations=100000).derive(PASSWORD.encode())
    iv = secrets.token_bytes(16)
    encryptor = Cipher(algorithms.AES(key), modes.CFB(iv)).encryptor()
    return iv + encryptor.update(stream.getvalue()) + encryptor.finalize()


def inspect(encrypted: bytes, **overrides: object) -> dict:
    kwargs = {
        "expected_encrypted_bytes": len(encrypted),
        "expected_encrypted_sha256": hashlib.sha256(encrypted).hexdigest(),
        "password": PASSWORD,
        "salt": SALT,
        "iterations": 100000,
        "limits": LIMITS,
    }
    kwargs.update(overrides)
    return inventory_encrypted_bundle(encrypted, **kwargs)


class AppWorldEncryptedBundleInventoryTests(unittest.TestCase):
    def test_valid_fixture_returns_aggregate_and_hashes_only(self) -> None:
        result = inspect(encrypted_fixture())
        self.assertEqual(result["member_count"], 2)
        self.assertEqual(result["extension_counts"], {".py": 2})
        self.assertTrue(result["decrypted_in_memory_only"])
        self.assertFalse(result["source_extracted"])
        self.assertFalse(result["protected_plaintext_persisted"])
        self.assertNotIn("relative_path", result["hashed_members"][0])

    def test_identity_mismatch_stops_before_decryption(self) -> None:
        encrypted = encrypted_fixture()
        with self.assertRaisesRegex(ValueError, "byte size mismatch"):
            inspect(encrypted, expected_encrypted_bytes=len(encrypted) + 1)
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            inspect(encrypted, expected_encrypted_sha256="0" * 64)

    def test_wrong_crypto_material_stops_as_invalid_zip(self) -> None:
        with self.assertRaisesRegex(ValueError, "valid ZIP"):
            inspect(encrypted_fixture(), password="wrong")

    def test_unsafe_path_stops_without_extraction(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsafe protected member path"):
            inspect(encrypted_fixture(unsafe=True))

    def test_duplicate_member_stops(self) -> None:
        with self.assertWarns(UserWarning):
            encrypted = encrypted_fixture(duplicate=True)
        with self.assertRaisesRegex(ValueError, "duplicate protected member"):
            inspect(encrypted)

    def test_symbolic_link_member_stops(self) -> None:
        with self.assertRaisesRegex(ValueError, "symbolic-link"):
            inspect(encrypted_fixture(symlink=True))

    def test_member_and_total_limits_stop(self) -> None:
        encrypted = encrypted_fixture()
        with self.assertRaisesRegex(ValueError, "member count"):
            inspect(encrypted, limits={**LIMITS, "maximum_member_count": 1})
        with self.assertRaisesRegex(ValueError, "total size"):
            inspect(encrypted, limits={**LIMITS, "maximum_total_uncompressed_bytes": 1})


if __name__ == "__main__":
    unittest.main()
