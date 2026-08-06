import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; RUNNER=ROOT/"experiments/proper_v2_3/run_appworld_static_api_inventory_remote_v2_3.py"
class RunnerTests(unittest.TestCase):
 def setUp(self): self.s=RUNNER.read_text(encoding="utf-8")
 def test_revision_clean_external_and_dependency_preflight(self):
  for token in ("project_revision_matches","tracked_worktree_clean","wheel_is_absolute_external","dependency_target_is_absolute_external","dependency_versions_exact","all_frozen_inputs_match"): self.assertIn(token,self.s)
 def test_exact_apps_member_and_identity_only(self): self.assertIn('archive.read(bundle["wheel_member_path"])',self.s); self.assertIn("apps bundle identity mismatch",self.s); self.assertNotIn("tests.bundle",self.s)
 def test_no_network_appworld_import_or_execution(self):
  for token in ("requests","urllib","import appworld","subprocess.run([sys.executable") : self.assertNotIn(token,self.s)
 def test_decryption_boundary_recorded_before_inventory(self): self.assertLess(self.s.index("decrypted=True"),self.s.index("inventory=inventory_encrypted_static_api_bundle"))
 def test_only_hash_inventory_and_closed_scientific_boundaries(self):
  for token in ('"protected_plaintext_persisted":False','"source_extracted":False','"module_imported":False','"model_loaded":False','"gpu_used":False','"target_selection_authorized":False'): self.assertIn(token,self.s)
if __name__=="__main__": unittest.main()
