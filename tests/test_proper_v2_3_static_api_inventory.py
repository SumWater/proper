from __future__ import annotations
import json,unittest
from src.failure_memory.proper_v2.v2_3.static_api_inventory import StaticApiInventoryError,inventory_static_api_sources

class StaticInventoryTests(unittest.TestCase):
 def test_pure_callable_is_read_only(self):
  value=inventory_static_api_sources({"a.py":b"def public(x):\n return len(x)\n"}); self.assertEqual(value["effect_counts"]["read_only"],1)
 def test_deterministic_self_assignment_is_idempotent(self):
  value=inventory_static_api_sources({"a.py":b"class A:\n def set_value(self, value):\n  self.value = value\n"}); self.assertEqual(value["effect_counts"]["idempotent_state_setting"],1)
 def test_cardinality_mutation_is_non_idempotent(self):
  value=inventory_static_api_sources({"a.py":b"class A:\n def add_value(self, value):\n  self.values.append(value)\n"}); self.assertEqual(value["effect_counts"]["non_idempotent_side_effect"],1)
 def test_unknown_external_call_has_priority(self):
  value=inventory_static_api_sources({"a.py":b"def public(x):\n return client.execute(x)\n"}); self.assertEqual(value["effect_counts"]["unknown_effect"],1); self.assertFalse(value["full_effect_coverage"])
 def test_unproven_mutation_receiver_is_unknown_not_persistent(self):
  value=inventory_static_api_sources({"a.py":b"def public(values, x):\n values.append(x)\n"}); self.assertEqual(value["effect_counts"]["unknown_effect"],1); self.assertEqual(value["effect_counts"]["non_idempotent_side_effect"],0)
 def test_transitive_private_helper_effect_is_propagated(self):
  source=b"class A:\n def public(self, x):\n  self._helper(x)\n def _helper(self, x):\n  self.values.append(x)\n"
  value=inventory_static_api_sources({"a.py":source}); self.assertEqual(value["candidate_count"],1); self.assertEqual(value["effect_counts"]["non_idempotent_side_effect"],1)
 def test_parse_or_utf8_failure_stops_complete_registry(self):
  for source in (b"def broken(: pass",b"\xff"):
   with self.assertRaises(StaticApiInventoryError): inventory_static_api_sources({"a.py":source})
 def test_private_callables_excluded_but_all_files_parsed(self):
  value=inventory_static_api_sources({"a.py":b"def _private(): pass\ndef public(): pass\n","b.pyi":b"def stub(x: int) -> int: ...\n","note.md":b"ignored"}); self.assertEqual(value["python_member_count"],2); self.assertEqual(value["candidate_count"],2)
 def test_output_is_hash_only_and_deterministic(self):
  source={"secret/path.py":b"def sensitive_name(secret_argument):\n return secret_argument\n"}; a=inventory_static_api_sources(source); b=inventory_static_api_sources(source); self.assertEqual(a,b); encoded=json.dumps(a); self.assertNotIn("secret/path",encoded); self.assertNotIn("sensitive_name",encoded); self.assertNotIn("secret_argument",encoded)
 def test_empty_python_inventory_stops(self):
  with self.assertRaises(StaticApiInventoryError): inventory_static_api_sources({"readme.md":b"x"})

if __name__=="__main__": unittest.main()
