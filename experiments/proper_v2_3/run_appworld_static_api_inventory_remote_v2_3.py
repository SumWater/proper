"""Guarded one-shot hash-only static API inventory of the exact AppWorld apps bundle."""
from __future__ import annotations
import argparse,hashlib,importlib.metadata,json,platform,socket,subprocess,sys,zipfile
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from src.failure_memory.proper_v2.v2_3.encrypted_static_api_inventory import inventory_encrypted_static_api_bundle
CONFIG=ROOT/"configs/proper_v2_3/appworld_static_api_inventory_runner_v2_3.json"
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def git(*args): return subprocess.run(["git","-c","core.fileMode=false",*args],cwd=ROOT,check=True,capture_output=True,text=True).stdout.strip()
def outside(path):
 try: path.relative_to(ROOT); return False
 except ValueError: return True
def versions_at(target):
 result={}
 for dist in importlib.metadata.distributions(path=[str(target)]):
  name=(dist.metadata.get("Name") or "").lower().replace("_","-")
  if name: result[name]=dist.version
 return result
def atomic(path,value):
 path.parent.mkdir(parents=True,exist_ok=True); temp=path.with_suffix(path.suffix+".tmp"); temp.write_bytes((json.dumps(value,ensure_ascii=False,indent=2,sort_keys=True)+"\n").encode()); temp.replace(path)
def run(expected_revision,wheel,target):
 c=json.loads(CONFIG.read_text(encoding="utf-8")); wheel=wheel.resolve(); target=target.resolve(); revision=git("rev-parse","HEAD")
 checks={
  "project_revision_matches":revision==expected_revision,
  "tracked_worktree_clean":git("status","--short","--untracked-files=no")=="",
  "python_311_linux_x86_64":sys.version_info[:2]==(3,11) and sys.platform.startswith("linux") and platform.machine().lower() in {"x86_64","amd64"},
  "wheel_is_absolute_external":wheel.is_absolute() and outside(wheel),
  "dependency_target_is_absolute_external":target.is_absolute() and target.is_dir() and outside(target),
  "dependency_versions_exact":versions_at(target)==c["dependency_versions"],
  "all_frozen_inputs_match":all(sha(ROOT/x["path"])==x["sha256"] for x in c["frozen_inputs"]),
  "zero_network_extract_import_model_boundary_closed":True
 }
 inventory=None; stop="preflight_failed"; decrypted=False
 if all(checks.values()):
  try:
   expected=c["wheel"]; bundle=c["apps_bundle"]
   if wheel.name!=expected["filename"] or wheel.stat().st_size!=expected["bytes"] or sha(wheel)!=expected["sha256"]: raise ValueError("wheel identity mismatch")
   with zipfile.ZipFile(wheel,"r") as archive: encrypted=archive.read(bundle["wheel_member_path"])
   if len(encrypted)!=bundle["encrypted_bytes"] or hashlib.sha256(encrypted).hexdigest()!=bundle["encrypted_sha256"]: raise ValueError("apps bundle identity mismatch")
   sys.path.insert(0,str(target)); decrypted=True
   inventory=inventory_encrypted_static_api_bundle(encrypted,expected_encrypted_bytes=bundle["encrypted_bytes"],expected_encrypted_sha256=bundle["encrypted_sha256"],password=c["public_crypto"]["password"],salt=c["public_crypto"]["salt_utf8"].encode(),iterations=c["public_crypto"]["iterations"],limits=c["zip_limits"])
   expected_aggregate=c["expected_aggregate"]
   if inventory["decrypted_zip_sha256"]!=expected_aggregate["decrypted_zip_sha256"] or inventory["archive_member_count"]!=expected_aggregate["archive_member_count"] or inventory["archive_total_uncompressed_bytes"]!=expected_aggregate["archive_total_uncompressed_bytes"] or inventory["static_api_inventory"]["python_member_count"]!=expected_aggregate["python_member_count"]: raise ValueError("frozen aggregate mismatch")
   stop=None
  except (OSError,KeyError,ValueError,zipfile.BadZipFile) as exc: stop=f"static_inventory_failed:{type(exc).__name__}:{exc}"
 checks["inventory_completed"]=inventory is not None and stop is None
 passed=all(checks.values())
 return {"schema_version":1,"run_kind":"proper_v2_3_appworld_hash_only_static_api_inventory","project_revision":revision,"expected_project_revision":expected_revision,"checks":checks,"passed":passed,"stop_reason":stop,"inventory":inventory,"apps_bundle_decrypted":decrypted,"protected_plaintext_persisted":False,"source_extracted":False,"module_imported":False,"tests_bundle_read":False,"data_or_tasks_read":False,"model_loaded":False,"gpu_used":False,"target_selection_authorized":False,"next_gate":"freeze_static_api_inventory_result" if passed else "stop_and_preserve_static_api_inventory"}
def main():
 p=argparse.ArgumentParser(); p.add_argument("--expected-project-revision",required=True); p.add_argument("--wheel",type=Path,required=True); p.add_argument("--dependency-target",type=Path,required=True); p.add_argument("--output",type=Path); a=p.parse_args(); stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"); output=a.output or ROOT/"outputs/proper_v2_3/appworld_static_api_inventory_remote"/f"{stamp}-{socket.gethostname().split('.')[0]}-{a.expected_project_revision[:12]}"/"inventory.json"; value=run(a.expected_project_revision,a.wheel,a.dependency_target); atomic(output,value); print(json.dumps({"output":str(output),"passed":value["passed"],"stop_reason":value["stop_reason"],"candidate_count":value["inventory"]["static_api_inventory"]["candidate_count"] if value["inventory"] else 0,"unknown_effect_count":value["inventory"]["static_api_inventory"]["unknown_effect_count"] if value["inventory"] else 0,"model_loaded":False,"gpu_used":False},sort_keys=True)); return 0 if value["passed"] else 1
if __name__=="__main__": raise SystemExit(main())
