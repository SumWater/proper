"""Freeze and independently audit the successful aggregate apps inventory."""
from __future__ import annotations
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
CONFIG=ROOT/"configs/proper_v2_3/appworld_apps_bundle_inventory_result_freeze_v2_3.json"
SCHEMA=ROOT/"schemas/proper_v2_3/appworld_apps_bundle_inventory_result_freeze.schema.json"
OUTPUT=ROOT/"outputs/proper_v2_3/appworld_apps_bundle_inventory_result_freeze/validation.json"
def load(path): return json.loads(path.read_text(encoding="utf-8"))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    config,schema=load(CONFIG),load(SCHEMA); run=config["run"]; provisioning=load(ROOT/run["provisioning_path"]); result=load(ROOT/run["inventory_path"]); inventory=result["inventory"]; records=inventory["hashed_members"]
    tests=subprocess.run([sys.executable,"-m","unittest","tests.test_proper_v2_3_appworld_apps_bundle_inventory_result_freeze"],cwd=ROOT,capture_output=True,text=True,check=False)
    canonical=hashlib.sha256(json.dumps(records,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    checks={
      "returned_artifact_bytes_and_hashes_match":all((ROOT/run[f"{k}_path"]).stat().st_size==run[f"{k}_bytes"] and sha(ROOT/run[f"{k}_path"])==run[f"{k}_sha256"] for k in ("provisioning","inventory")),
      "all_frozen_inputs_match":all(sha(ROOT/x["path"])==x["sha256"] for x in config["frozen_inputs"]),
      "offline_provisioning_and_inventory_passed":provisioning["status"]=="inventory_completed" and provisioning["inventory_returncode"]==0 and result["passed"] and all(result["checks"].values()),
      "revision_matches_both_artifacts":provisioning["project_revision"]==result["project_revision"]==run["project_revision"],
      "expected_aggregate_matches":all(inventory[k]==v for k,v in config["expected_inventory"].items()),
      "member_count_total_and_manifest_recompute":len(records)==inventory["member_count"] and sum(x["uncompressed_bytes"] for x in records)==inventory["total_uncompressed_bytes"] and canonical==inventory["hashed_member_manifest_sha256"],
      "records_are_sorted_and_hash_only":records==sorted(records,key=lambda x:x["path_sha256"]) and all(set(x)=={"path_sha256","content_sha256","uncompressed_bytes","compressed_bytes"} for x in records),
      "plaintext_extraction_task_model_gpu_boundaries_closed":not any(result[k] for k in ("protected_plaintext_persisted","source_extracted","task_or_api_data_read","model_loaded","gpu_used")),
      "candidate_and_scientific_claims_remain_unmeasured":not any(config["interpretation"][k] for k in ("api_effect_coverage_measured","task_inventory_measured","candidate_capacity_measured","heldout_status_established","scientific_stage_passed")),
      "rerun_model_and_confirmatory_gates_closed":not any(config["disposition"][k] for k in ("bundle_inventory_rerun_authorized","model_run_authorized","confirmatory_claim_authorized")),
      "five_freeze_tests_pass":tests.returncode==0 and "Ran 5 tests" in tests.stderr,
      "freeze_schema_is_closed":schema["additionalProperties"] is False and set(schema["required"])==set(schema["properties"])
    }
    value={"schema_version":1,"run_kind":"proper_v2_3_appworld_apps_bundle_inventory_result_freeze","passed":all(checks.values()),"checks":checks,"freeze_config_sha256":sha(CONFIG),"provisioning_sha256":sha(ROOT/run["provisioning_path"]),"inventory_sha256":sha(ROOT/run["inventory_path"]),"remote_project_revision":run["project_revision"],"member_count":inventory["member_count"],"total_uncompressed_bytes":inventory["total_uncompressed_bytes"],"hashed_member_manifest_sha256":inventory["hashed_member_manifest_sha256"],"apps_bundle_decrypted":True,"protected_plaintext_persisted":False,"source_extracted":False,"task_or_api_data_read":False,"model_loaded":False,"gpu_used":False,"scientific_stage_passed":False,"bundle_inventory_rerun_authorized":False,"static_api_protocol_design_authorized":all(checks.values()),"model_run_authorized":False,"confirmatory_claim_authorized":False,"next_gate":"design_in_memory_static_api_inventory_protocol"}
    checks["validation_matches_closed_schema_fields"]=set(value)==set(schema["required"]); value["passed"]=all(checks.values()); value["static_api_protocol_design_authorized"]=value["passed"]
    OUTPUT.parent.mkdir(parents=True,exist_ok=True); OUTPUT.write_bytes((json.dumps(value,ensure_ascii=False,indent=2,sort_keys=True)+"\n").encode()); print(json.dumps(value,sort_keys=True)); return 0 if value["passed"] else 1
if __name__=="__main__": raise SystemExit(main())
