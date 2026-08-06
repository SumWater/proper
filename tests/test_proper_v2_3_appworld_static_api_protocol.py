import json,unittest
from pathlib import Path
from experiments.proper_v2_3.scripted_appworld_static_api_protocol_v2_3 import run_traces
ROOT=Path(__file__).resolve().parents[1]; CONFIG=ROOT/"configs/proper_v2_3/appworld_in_memory_static_api_inventory_protocol_v2_3.json"
class ProtocolTests(unittest.TestCase):
 def setUp(self): self.c=json.loads(CONFIG.read_text(encoding="utf-8")); self.t=run_traces()
 def test_complete_ast_registry_precedes_selection(self): self.assertTrue(self.c["candidate_registry"]["complete_superset_before_selection"]); self.assertFalse(self.c["candidate_registry"]["target_selection_in_this_stage"])
 def test_proof_rules_cover_taxonomy_conservatively(self): self.assertEqual(set(self.c["effect_proof_rules"])-{"priority"},{"read_only","idempotent_state_setting","non_idempotent_side_effect","unknown_effect"}); self.assertEqual(self.c["effect_proof_rules"]["priority"][0],"unknown_effect")
 def test_privacy_and_hidden_fields_closed(self): self.assertFalse(self.c["privacy_output"]["persist_symbol_or_path_plaintext"]); self.assertIn("benchmark_gold_label",self.c["observable_evidence"]["forbidden"])
 def test_unknown_and_parse_errors_stop_claim_or_run(self): self.assertEqual(self.c["stop_rules"]["unknown_effect"],"report_partial_inventory_and_block_full_capacity"); self.assertEqual(self.c["budgets"]["parse_failures"],0)
 def test_eight_traces_cover_effects_and_stops(self): self.assertEqual(len(self.t),8); self.assertEqual({x["effect"] for x in self.t if x["effect"]},{"read_only","idempotent_state_setting","non_idempotent_side_effect","unknown_effect"}); self.assertTrue({"stop_and_preserve","stop_privacy_boundary","stop_protocol_boundary"}<={x["decision"] for x in self.t})
if __name__=="__main__": unittest.main()
