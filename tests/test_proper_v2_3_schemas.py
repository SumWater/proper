from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
EXPERIMENTS = ROOT / "experiments" / "proper_v2_3"
for path in (SRC, EXPERIMENTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripted_traces_v2_3 import (
    run_scripted_traces,
    trace_consumption_and_handoff,
)


class ProperV23SchemaTests(unittest.TestCase):
    def test_schemas_parse_and_close_top_level_objects(self) -> None:
        for name in (
            "action_execution_ledger.schema.json",
            "controller_decision.schema.json",
        ):
            schema = json.loads(
                (ROOT / "schemas/proper_v2_3" / name).read_text(encoding="utf-8")
            )
            self.assertFalse(schema["additionalProperties"])
            self.assertEqual(schema["properties"]["schema_version"]["const"], 1)

    def test_generated_mappings_have_all_top_level_required_fields(self) -> None:
        trace = trace_consumption_and_handoff()
        ledger_schema = json.loads(
            (
                ROOT
                / "schemas/proper_v2_3/action_execution_ledger.schema.json"
            ).read_text(encoding="utf-8")
        )
        decision_schema = json.loads(
            (
                ROOT / "schemas/proper_v2_3/controller_decision.schema.json"
            ).read_text(encoding="utf-8")
        )
        self.assertTrue(
            set(ledger_schema["required"]).issubset(trace["ledger"].keys())
        )
        self.assertTrue(
            set(decision_schema["required"]).issubset(
                trace["repeat_decision"].keys()
            )
        )

    def test_generated_mappings_validate_with_draft_2020_12(self) -> None:
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is not installed locally")
        traces = run_scripted_traces()["traces"]
        ledger_schema = json.loads(
            (
                ROOT
                / "schemas/proper_v2_3/action_execution_ledger.schema.json"
            ).read_text(encoding="utf-8")
        )
        decision_schema = json.loads(
            (
                ROOT / "schemas/proper_v2_3/controller_decision.schema.json"
            ).read_text(encoding="utf-8")
        )
        jsonschema.Draft202012Validator.check_schema(ledger_schema)
        jsonschema.Draft202012Validator.check_schema(decision_schema)
        ledger_validator = jsonschema.Draft202012Validator(ledger_schema)
        decision_validator = jsonschema.Draft202012Validator(decision_schema)
        decision_count = 0
        for trace in traces:
            ledger_validator.validate(trace["ledger"])
            for value in trace.values():
                if not isinstance(value, dict):
                    continue
                if value.get("method_version") != (
                    "proper_v2_3_execution_controller_development"
                ):
                    continue
                decision_validator.validate(value)
                decision_count += 1
        self.assertGreaterEqual(decision_count, 5)


if __name__ == "__main__":
    unittest.main()
