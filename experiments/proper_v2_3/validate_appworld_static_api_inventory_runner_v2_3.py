"""Freeze the guarded runner before its single real bundle invocation."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; CONFIG=ROOT/"configs/proper_v2_3/appworld_static_api_inventory_runner_v2_3.json"; SCHEMA=ROOT/"schemas/proper_v2_3/appworld_static_api_inventory_runner_validation.schema.json"; RUN_SCHEMA=ROOT/"schemas/proper_v2_3/appworld_static_api_inventory_run.schema.json"; OUTPUT=ROOT/"outputs/proper_v2_3/appworld_static_api_inventory_runner/validation.json"
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 c=json.loads(CONFIG.read_text(encoding="utf-8")); s=json.loads(SCHEMA.read_text(encoding="utf-8")); rs=json.loads(RUN_SCHEMA.read_text(encoding="utf-8")); runner=(ROOT/"experiments/proper_v2_3/run_appworld_static_api_inventory_remote_v2_3.py").read_text(encoding="utf-8")
 tests=subprocess.run([sys.executable,"-W","error","-m","unittest","tests.test_proper_v2_3_encrypted_static_api_inventory","tests.test_proper_v2_3_appworld_static_api_inventory_runner"],cwd=ROOT,capture_output=True,text=True,check=False); prep=subprocess.run([sys.executable,"-m","unittest","tests.test_proper_v2_3_appworld_static_api_inventory_runner_preparation"],cwd=ROOT,capture_output=True,text=True,check=False)
 checks={
  "all_frozen_inputs_match":all(sha(ROOT/x["path"])==x["sha256"] for x in c["frozen_inputs"]),
  "exact_wheel_bundle_crypto_aggregate_and_dependencies":c["apps_bundle"]["encrypted_sha256"]=="ba58bc5679c3573aa8f60ad6f5cda4377128a0ec569de5eef9543a77561796bb" and c["expected_aggregate"]["python_member_count"]==72 and c["dependency_versions"]["cryptography"]=="49.0.0",
  "runner_is_revision_clean_external_and_dependency_guarded":all(token in runner for token in ("project_revision_matches","tracked_worktree_clean","wheel_is_absolute_external","dependency_target_is_absolute_external","dependency_versions_exact","all_frozen_inputs_match")),
  "runner_reads_only_exact_apps_member":'archive.read(bundle["wheel_member_path"])' in runner and "tests.bundle" not in runner,
  "runner_has_no_network_appworld_import_or_subprocess_execution":all(token not in runner for token in ("requests","urllib","import appworld","subprocess.run([sys.executable")),
  "decryption_is_recorded_before_inventory_call":runner.index("decrypted=True")<runner.index("inventory=inventory_encrypted_static_api_bundle"),
  "result_schema_is_closed_and_hash_inventory_referenced":rs["additionalProperties"] is False and "$ref" in rs["properties"]["inventory"]["oneOf"][1]["properties"]["static_api_inventory"],
  "twelve_synthetic_and_runner_tests_pass_without_warning":tests.returncode==0 and "Ran 12 tests" in tests.stderr,
  "three_preparation_tests_pass":prep.returncode==0 and "Ran 3 tests" in prep.stderr,
  "zero_network_extract_import_model_gpu_and_selection_budgets":all(c["budgets"][k]==0 for k in ("network_requests","source_extractions","module_imports","model_requests","gpu_operations","target_selections")),
  "one_invocation_no_rerun_and_no_claims":c["budgets"]["remote_invocations"]==1 and c["authority"]["one_real_hash_only_static_inventory"] and not any(c["authority"][k] for k in ("rerun","model","gpu","heldout_claim","confirmatory_claim")),
  "validation_schema_is_closed":s["additionalProperties"] is False and set(s["required"])==set(s["properties"])
 }
 v={"schema_version":1,"run_kind":"proper_v2_3_appworld_static_api_inventory_runner_validation","passed":all(checks.values()),"checks":checks,"config_sha256":sha(CONFIG),"runner_sha256":sha(ROOT/"experiments/proper_v2_3/run_appworld_static_api_inventory_remote_v2_3.py"),"tests_run":12,"synthetic_bundle_decrypted":True,"real_bundle_decrypted":False,"source_persisted":False,"model_loaded":False,"gpu_used":False,"one_remote_inventory_authorized":all(checks.values()),"next_gate":"run_one_real_hash_only_static_api_inventory" if all(checks.values()) else "stop_static_api_runner"}
 OUTPUT.parent.mkdir(parents=True,exist_ok=True); OUTPUT.write_bytes((json.dumps(v,indent=2,sort_keys=True)+"\n").encode()); print(json.dumps(v,sort_keys=True)); return 0 if v["passed"] else 1
if __name__=="__main__": raise SystemExit(main())
