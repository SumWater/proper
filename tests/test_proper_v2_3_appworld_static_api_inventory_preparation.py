import hashlib,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; CONFIG=ROOT/"configs/proper_v2_3/appworld_static_api_inventory_implementation_v2_3.json"
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
class PreparationTests(unittest.TestCase):
 def setUp(self): self.c=json.loads(CONFIG.read_text(encoding="utf-8"))
 def test_all_inputs_are_exact(self):
  for item in self.c["frozen_inputs"]: self.assertEqual(sha(ROOT/item["path"]),item["sha256"],item["path"])
 def test_real_run_stays_closed_until_runner_freeze(self): self.assertFalse(self.c["authority"]["one_real_in_memory_static_inventory_after_runner_freeze"]); self.assertTrue(self.c["authority"]["runner_implementation_next"])
 def test_claim_and_model_boundaries_closed(self): self.assertFalse(any(self.c["authority"][k] for k in ("target_selection","model","gpu","heldout_claim","confirmatory_claim")))
if __name__=="__main__": unittest.main()
