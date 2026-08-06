import hashlib,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; CONFIG=ROOT/"configs/proper_v2_3/appworld_static_api_inventory_runner_v2_3.json"
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
class PreparationTests(unittest.TestCase):
 def setUp(self): self.c=json.loads(CONFIG.read_text(encoding="utf-8"))
 def test_all_frozen_inputs_match(self):
  for item in self.c["frozen_inputs"]: self.assertEqual(sha(ROOT/item["path"]),item["sha256"],item["path"])
 def test_exact_aggregate_and_dependency_environment(self): self.assertEqual(self.c["expected_aggregate"]["python_member_count"],72); self.assertEqual(self.c["dependency_versions"],{"cffi":"2.0.0","cryptography":"49.0.0","pycparser":"2.23"})
 def test_one_shot_and_all_scientific_boundaries_closed(self): self.assertTrue(self.c["authority"]["one_real_hash_only_static_inventory"]); self.assertFalse(any(self.c["authority"][k] for k in ("rerun","tests_data_or_tasks","model","gpu","heldout_claim","confirmatory_claim")))
if __name__=="__main__": unittest.main()
