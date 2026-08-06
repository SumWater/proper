from __future__ import annotations
import hashlib,json,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/"configs/proper_v2_3/appworld_apps_bundle_inventory_result_freeze_v2_3.json"
def load(path): return json.loads(path.read_text(encoding="utf-8"))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

class FreezeTests(unittest.TestCase):
    def setUp(self):
        self.config=load(CONFIG); run=self.config["run"]
        self.provisioning=load(ROOT/run["provisioning_path"]); self.result=load(ROOT/run["inventory_path"])
    def test_exact_artifact_hashes(self):
        run=self.config["run"]
        for kind in ("provisioning","inventory"):
            path=ROOT/run[f"{kind}_path"]
            self.assertEqual(path.stat().st_size,run[f"{kind}_bytes"]); self.assertEqual(sha(path),run[f"{kind}_sha256"])
        for item in self.config["frozen_inputs"]: self.assertEqual(sha(ROOT/item["path"]),item["sha256"])
    def test_provisioning_and_inventory_passed(self):
        self.assertEqual(self.provisioning["status"],"inventory_completed"); self.assertEqual(self.provisioning["inventory_returncode"],0)
        self.assertTrue(self.result["passed"]); self.assertTrue(all(self.result["checks"].values()))
    def test_aggregate_recomputes(self):
        inventory=self.result["inventory"]; records=inventory["hashed_members"]
        canonical=hashlib.sha256(json.dumps(records,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        self.assertEqual(len(records),inventory["member_count"]); self.assertEqual(sum(x["uncompressed_bytes"] for x in records),inventory["total_uncompressed_bytes"]); self.assertEqual(canonical,inventory["hashed_member_manifest_sha256"])
    def test_expected_inventory_matches(self):
        inventory=self.result["inventory"]
        for key,value in self.config["expected_inventory"].items(): self.assertEqual(inventory[key],value,key)
    def test_privacy_model_and_claim_gates(self):
        self.assertTrue(self.result["apps_bundle_decrypted"]); self.assertFalse(any(self.result[k] for k in ("protected_plaintext_persisted","source_extracted","task_or_api_data_read","model_loaded","gpu_used")))
        self.assertFalse(self.config["disposition"]["bundle_inventory_rerun_authorized"]); self.assertFalse(self.config["disposition"]["model_run_authorized"]); self.assertFalse(self.config["disposition"]["confirmatory_claim_authorized"])

if __name__=="__main__": unittest.main()
