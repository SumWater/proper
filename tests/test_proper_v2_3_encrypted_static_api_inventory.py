from __future__ import annotations
import hashlib,io,json,stat,unittest,warnings,zipfile
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher,algorithms
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
try:
 from cryptography.hazmat.decrepit.ciphers import modes
except ImportError:
 from cryptography.hazmat.primitives.ciphers import modes
from src.failure_memory.proper_v2.v2_3.encrypted_static_api_inventory import inventory_encrypted_static_api_bundle

LIMITS={"maximum_member_count":20,"maximum_member_uncompressed_bytes":10000,"maximum_total_uncompressed_bytes":50000,"maximum_compression_ratio":500}
def encrypted_zip(files):
 buffer=io.BytesIO()
 with zipfile.ZipFile(buffer,"w",zipfile.ZIP_DEFLATED) as z:
  for name,content in files: z.writestr(name,content)
 plain=buffer.getvalue(); iv=b"0"*16; key=PBKDF2HMAC(algorithm=hashes.SHA256(),length=32,salt=b"salt",iterations=100).derive(b"password"); enc=Cipher(algorithms.AES(key),modes.CFB(iv)).encryptor(); encrypted=iv+enc.update(plain)+enc.finalize(); return encrypted,plain
def run(files,limits=LIMITS):
 encrypted,_=encrypted_zip(files); return inventory_encrypted_static_api_bundle(encrypted,expected_encrypted_bytes=len(encrypted),expected_encrypted_sha256=hashlib.sha256(encrypted).hexdigest(),password="password",salt=b"salt",iterations=100,limits=limits)
class EncryptedStaticTests(unittest.TestCase):
 def test_success_is_hash_only(self):
  value=run([("secret/a.py",b"def public(x):\n return len(x)\n"),("secret/a.pyi",b"def stub(x: int) -> int: ...\n"),("note.md",b"hidden")]); encoded=json.dumps(value); self.assertEqual(value["static_api_inventory"]["python_member_count"],2); self.assertNotIn("secret/a",encoded); self.assertNotIn("public",encoded); self.assertFalse(value["protected_plaintext_persisted"])
 def test_effect_classes_flow_through(self):
  value=run([("a.py",b"class A:\n def set(self,x): self.x=x\n def add(self,x): self.xs.append(x)\n")]); self.assertEqual(value["static_api_inventory"]["effect_counts"]["idempotent_state_setting"],1); self.assertEqual(value["static_api_inventory"]["effect_counts"]["non_idempotent_side_effect"],1)
 def test_identity_mismatch_stops_before_decryption(self):
  encrypted,_=encrypted_zip([("a.py",b"def x(): pass")])
  with self.assertRaises(ValueError): inventory_encrypted_static_api_bundle(encrypted,expected_encrypted_bytes=len(encrypted),expected_encrypted_sha256="0"*64,password="password",salt=b"salt",iterations=100,limits=LIMITS)
 def test_unsafe_path_stops(self):
  with self.assertRaises(ValueError): run([("../escape.py",b"def x(): pass")])
 def test_duplicate_member_stops(self):
  with warnings.catch_warnings():
   warnings.simplefilter("ignore",UserWarning)
   with self.assertRaises(ValueError): run([("a.py",b"def a(): pass"),("a.py",b"def b(): pass")])
 def test_symlink_stops(self):
  buffer=io.BytesIO()
  with zipfile.ZipFile(buffer,"w") as z:
   info=zipfile.ZipInfo("link.py"); info.external_attr=(stat.S_IFLNK|0o777)<<16; z.writestr(info,b"target")
  plain=buffer.getvalue(); iv=b"0"*16; key=PBKDF2HMAC(algorithm=hashes.SHA256(),length=32,salt=b"salt",iterations=100).derive(b"password"); enc=Cipher(algorithms.AES(key),modes.CFB(iv)).encryptor(); encrypted=iv+enc.update(plain)+enc.finalize()
  with self.assertRaises(ValueError): inventory_encrypted_static_api_bundle(encrypted,expected_encrypted_bytes=len(encrypted),expected_encrypted_sha256=hashlib.sha256(encrypted).hexdigest(),password="password",salt=b"salt",iterations=100,limits=LIMITS)
 def test_parse_failure_stops_without_partial_result(self):
  with self.assertRaises(ValueError): run([("a.py",b"def broken(: pass")])
if __name__=="__main__": unittest.main()
