import hashlib,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; CONFIG=ROOT/"configs/proper_v2_3/appworld_static_api_inventory_result_freeze_v2_3.json"
def load(p): return json.loads(p.read_text(encoding="utf-8"))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
class FreezeTests(unittest.TestCase):
 def setUp(self): self.c=load(CONFIG); self.r=load(ROOT/self.c["run"]["path"]); self.i=self.r["inventory"]["static_api_inventory"]
 def test_exact_result_and_inputs(self):
  run=self.c["run"]; path=ROOT/run["path"]; self.assertEqual(path.stat().st_size,run["bytes"]); self.assertEqual(sha(path),run["sha256"])
  for item in self.c["frozen_inputs"]: self.assertEqual(sha(ROOT/item["path"]),item["sha256"])
 def test_remote_execution_and_privacy_passed(self): self.assertTrue(self.r["passed"]); self.assertTrue(all(self.r["checks"].values())); self.assertFalse(any(self.r[k] for k in ("protected_plaintext_persisted","source_extracted","module_imported","tests_bundle_read","data_or_tasks_read","model_loaded","gpu_used")))
 def test_counts_and_manifest_recompute(self):
  records=self.i["candidate_records"]; counts={k:0 for k in self.i["effect_counts"]}
  for x in records: counts[x["effect_class"]]+=1
  manifest=hashlib.sha256(json.dumps(records,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest(); self.assertEqual(len(records),self.i["candidate_count"]); self.assertEqual(counts,self.i["effect_counts"]); self.assertEqual(manifest,self.i["candidate_manifest_sha256"])
 def test_capacity_gate_failed_without_refuting_source_or_method(self): self.assertFalse(self.i["full_effect_coverage"]); self.assertEqual(self.i["unknown_effect_count"],659); self.assertFalse(self.c["interpretation"]["appworld_task_capacity_refuted"]); self.assertFalse(self.c["interpretation"]["proper_method_assessed"])
 def test_rerun_tuning_selection_model_and_claims_stopped(self): self.assertTrue(self.c["disposition"]["appworld_source_route_stopped"]); self.assertFalse(any(self.c["disposition"][k] for k in ("inventory_rerun_authorized","post_result_rule_tuning_authorized","target_selection_authorized","model_run_authorized","confirmatory_claim_authorized")))
if __name__=="__main__": unittest.main()
