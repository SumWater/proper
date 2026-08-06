"""Validate static API inventory design without opening the real bundle."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; CONFIG=ROOT/"configs/proper_v2_3/appworld_in_memory_static_api_inventory_protocol_v2_3.json"; SCHEMA=ROOT/"schemas/proper_v2_3/appworld_in_memory_static_api_inventory_protocol_validation.schema.json"; OUTPUT=ROOT/"outputs/proper_v2_3/appworld_static_api_protocol/validation.json"
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 c=json.loads(CONFIG.read_text(encoding="utf-8")); s=json.loads(SCHEMA.read_text(encoding="utf-8")); from experiments.proper_v2_3.scripted_appworld_static_api_protocol_v2_3 import run_traces
 traces=run_traces(); tests=subprocess.run([sys.executable,"-m","unittest","tests.test_proper_v2_3_appworld_static_api_protocol"],cwd=ROOT,capture_output=True,text=True,check=False)
 checks={
  "all_frozen_inputs_match":all(sha(ROOT/x["path"])==x["sha256"] for x in c["frozen_inputs"]),
  "exact_apps_bundle_ast_only_boundary":c["input_boundary"]["exact_apps_bundle_only"] and c["input_boundary"]["parse_with_standard_ast"] if "parse_with_standard_ast" in c["input_boundary"] else c["candidate_registry"]["parse_with_standard_ast"],
  "complete_callable_superset_before_selection":c["candidate_registry"]["scan_every_python_and_stub_member"] and c["candidate_registry"]["complete_superset_before_selection"] and not c["candidate_registry"]["target_selection_in_this_stage"],
  "observable_evidence_excludes_hidden_gold_and_scenario_fields":set(("scenario_name","semantic_family","benchmark_gold_label","hidden_recoverability","gold_action","evaluator_outcome"))<=set(c["observable_evidence"]["forbidden"]),
  "four_effect_proofs_and_retry_contracts_complete":set(c["effect_proof_rules"])-{"priority"}=={"read_only","idempotent_state_setting","non_idempotent_side_effect","unknown_effect"} and len(c["retry_contract"])==4,
  "unknown_has_conservative_priority_and_blocks_full_claim":c["effect_proof_rules"]["priority"][0]=="unknown_effect" and c["capacity_gate"]["any_unknown_blocks_full_capacity_claim"],
  "full_coverage_requires_three_known_classes_not_unknown":c["capacity_gate"]["required_known_effect_classes_for_full_coverage"]==["read_only","idempotent_state_setting","non_idempotent_side_effect"],
  "plaintext_names_docs_arguments_and_source_forbidden":not any(c["privacy_output"][k] for k in ("persist_symbol_or_path_plaintext","persist_docstrings_or_source","persist_argument_names")),
  "tests_data_tasks_import_network_model_closed":not any((c["input_boundary"]["tests_bundle"],c["input_boundary"]["data_or_tasks"],c["input_boundary"]["module_import"],c["input_boundary"]["network"],c["boundary"]["model_loaded"],c["boundary"]["gpu_used"])),
  "zero_parse_network_model_and_action_budgets":all(c["budgets"][k]==0 for k in ("parse_failures","network_requests","model_requests","native_actions")),
  "eight_traces_cover_taxonomy_privacy_parse_and_access_stops":len(traces)==8 and {x["effect"] for x in traces if x["effect"]}=={"read_only","idempotent_state_setting","non_idempotent_side_effect","unknown_effect"},
  "six_protocol_tests_pass":tests.returncode==0 and "Ran 6 tests" in tests.stderr,
  "closed_validation_schema":s["additionalProperties"] is False and set(s["required"])==set(s["properties"])
 }
 v={"schema_version":1,"run_kind":"proper_v2_3_appworld_in_memory_static_api_inventory_protocol_validation","passed":all(checks.values()),"checks":checks,"config_sha256":sha(CONFIG),"trace_count":8,"real_bundle_decrypted":False,"api_inventory_performed":False,"source_persisted":False,"task_read":False,"model_loaded":False,"gpu_used":False,"implementation_authorized":all(checks.values()),"next_gate":"implement_and_synthetically_validate_in_memory_static_api_inventory" if all(checks.values()) else "stop_static_api_protocol"}
 OUTPUT.parent.mkdir(parents=True,exist_ok=True); OUTPUT.write_bytes((json.dumps(v,indent=2,sort_keys=True)+"\n").encode()); print(json.dumps(v,sort_keys=True)); return 0 if v["passed"] else 1
if __name__=="__main__": raise SystemExit(main())
