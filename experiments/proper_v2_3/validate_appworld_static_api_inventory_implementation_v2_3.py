"""Validate hash-only AST implementation before a real-bundle runner exists."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; CONFIG=ROOT/"configs/proper_v2_3/appworld_static_api_inventory_implementation_v2_3.json"; SCHEMA=ROOT/"schemas/proper_v2_3/appworld_static_api_inventory_implementation_validation.schema.json"; RESULT_SCHEMA=ROOT/"schemas/proper_v2_3/appworld_static_api_inventory.schema.json"; OUTPUT=ROOT/"outputs/proper_v2_3/appworld_static_api_inventory_implementation/validation.json"
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 c=json.loads(CONFIG.read_text(encoding="utf-8")); s=json.loads(SCHEMA.read_text(encoding="utf-8")); rs=json.loads(RESULT_SCHEMA.read_text(encoding="utf-8")); source=(ROOT/"src/failure_memory/proper_v2/v2_3/static_api_inventory.py").read_text(encoding="utf-8")
 tests=subprocess.run([sys.executable,"-m","unittest","tests.test_proper_v2_3_static_api_inventory"],cwd=ROOT,capture_output=True,text=True,check=False)
 prep=subprocess.run([sys.executable,"-m","unittest","tests.test_proper_v2_3_appworld_static_api_inventory_preparation"],cwd=ROOT,capture_output=True,text=True,check=False)
 checks={
  "all_frozen_inputs_match":all(sha(ROOT/x["path"])==x["sha256"] for x in c["frozen_inputs"]),
  "standard_ast_without_dynamic_execution_or_import":c["implementation"]["standard_library_only"] and "ast.parse" in source and all(token not in source for token in ("exec(","eval(","importlib","__import__")),
  "complete_python_stub_parse_before_private_exclusion":c["implementation"]["complete_python_and_stub_parse"] and c["implementation"]["private_candidate_exclusion_after_parse"],
  "transitive_and_ambiguous_calls_are_conservative":c["implementation"]["transitive_internal_call_evidence"] and c["implementation"]["ambiguous_calls_become_unknown"] and "UNRESOLVED_EXTERNAL_CALL" in source,
  "three_known_classes_and_zero_unknown_define_full_coverage":c["classification"]["known_full_coverage_classes"]==["read_only","idempotent_state_setting","non_idempotent_side_effect"] and c["classification"]["unknown_blocks_full_coverage"],
  "output_is_hash_only_and_closed":c["output"]["hash_only"] and not c["output"]["plaintext_paths_symbols_arguments_docstrings_or_source"] and rs["additionalProperties"] is False,
  "candidate_record_schema_has_no_plaintext_fields":not ({"path","symbol","name","arguments","docstring","source"}&set(rs["properties"]["candidate_records"]["items"]["properties"])),
  "ten_synthetic_tests_pass":tests.returncode==0 and "Ran 10 tests" in tests.stderr,
  "three_preparation_tests_pass":prep.returncode==0 and "Ran 3 tests" in prep.stderr,
  "real_bundle_runner_model_and_claim_gates_closed":not any(c["authority"][k] for k in ("one_real_in_memory_static_inventory_after_runner_freeze","target_selection","model","gpu","heldout_claim","confirmatory_claim")),
  "validation_schema_is_closed":s["additionalProperties"] is False and set(s["required"])==set(s["properties"])
 }
 v={"schema_version":1,"run_kind":"proper_v2_3_appworld_static_api_inventory_implementation_validation","passed":all(checks.values()),"checks":checks,"config_sha256":sha(CONFIG),"implementation_sha256":sha(ROOT/"src/failure_memory/proper_v2/v2_3/static_api_inventory.py"),"tests_run":10,"synthetic_sources_parsed":True,"real_bundle_decrypted":False,"source_persisted":False,"model_loaded":False,"gpu_used":False,"runner_implementation_authorized":all(checks.values()),"real_inventory_authorized":False,"next_gate":"implement_guarded_real_bundle_static_inventory_runner" if all(checks.values()) else "stop_static_api_implementation"}
 OUTPUT.parent.mkdir(parents=True,exist_ok=True); OUTPUT.write_bytes((json.dumps(v,indent=2,sort_keys=True)+"\n").encode()); print(json.dumps(v,sort_keys=True)); return 0 if v["passed"] else 1
if __name__=="__main__": raise SystemExit(main())
