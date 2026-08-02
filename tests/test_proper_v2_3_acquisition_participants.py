from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.failure_memory.proper_v2.v2_3.acquisition_participants import (
    make_worker_request,
    parse_agent_output,
    parse_user_output,
    render_agent_system_prompt,
    render_user_system_prompt,
    serialize_agent_history,
    serialize_user_history,
)

PROMPTS = json.loads((ROOT / "configs/proper_v2_3/local_tau_participant_prompts_v2_3.json").read_text(encoding="utf-8"))
TOOLS = [{
    "name": "get_record",
    "description": "Read one public record.",
    "parameters": {
        "type": "object", "additionalProperties": False,
        "required": ["record_id"],
        "properties": {"record_id": {"type": "string"}},
    },
}]


class AcquisitionParticipantTests(unittest.TestCase):
    def test_agent_and_user_prompts_keep_private_context_separate(self) -> None:
        agent = render_agent_system_prompt(PROMPTS, public_policy="public policy", public_tools=TOOLS)
        user = render_user_system_prompt(PROMPTS, simulation_guidelines="guidelines", private_scenario="PRIVATE SCENARIO")
        self.assertNotIn("PRIVATE SCENARIO", agent)
        self.assertIn("PRIVATE SCENARIO", user)
        self.assertIn("public policy", agent)
        self.assertNotIn("public policy", user)

    def test_agent_history_encodes_public_tool_messages_as_user_input(self) -> None:
        history = [
            {"role": "user", "content": "look it up"},
            {"role": "assistant", "tool_calls": [{"id": "c1", "name": "get_record", "arguments": {"record_id": "r1"}}]},
            {"role": "tool", "tool_call_id": "c1", "content": {"value": 3}, "error": False},
        ]
        messages = serialize_agent_history("system", history)
        self.assertEqual([item["role"] for item in messages], ["system", "user", "assistant", "user"])
        self.assertIn("public_tool_result", messages[-1]["content"])

    def test_user_history_flips_agent_and_user_roles(self) -> None:
        history = [
            {"role": "assistant", "content": "How can I help?"},
            {"role": "user", "content": "Please check."},
        ]
        messages = serialize_user_history("system", history)
        self.assertEqual([item["role"] for item in messages], ["system", "user", "assistant"])

    def test_valid_agent_message_and_tool_outputs(self) -> None:
        self.assertEqual(parse_agent_output('{"kind":"message","content":"Done"}', TOOLS), {"kind": "message", "content": "Done"})
        self.assertEqual(
            parse_agent_output('{"kind":"tool","tool_name":"get_record","arguments":{"record_id":"r1"}}', TOOLS),
            {"kind": "tool", "tool_name": "get_record", "arguments": {"record_id": "r1"}},
        )

    def test_agent_rejects_unknown_tool_missing_argument_and_extra_fields(self) -> None:
        invalid = [
            '{"kind":"tool","tool_name":"gold_tool","arguments":{}}',
            '{"kind":"tool","tool_name":"get_record","arguments":{}}',
            '{"kind":"tool","tool_name":"get_record","arguments":{"record_id":3}}',
            '{"kind":"message","content":"x","evaluation_criteria":{}}',
        ]
        for raw in invalid:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_agent_output(raw, TOOLS)

    def test_user_output_is_strict_nonempty_message(self) -> None:
        self.assertEqual(parse_user_output('{"kind":"message","content":"Hello"}'), {"kind": "message", "content": "Hello"})
        for raw in ('not json', '{"kind":"tool","tool_name":"x","arguments":{}}', '{"kind":"message","content":""}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_user_output(raw)

    def test_worker_request_is_deterministic_and_role_limited(self) -> None:
        request = make_worker_request(
            request_id="p1:agent:step-1", messages=[{"role": "system", "content": "s"}, {"role": "user", "content": "u"}],
            seed=20260730, max_new_tokens=256,
        )
        self.assertEqual(request["seed"], 20260730)
        self.assertEqual(request["max_new_tokens"], 256)
        with self.assertRaises(ValueError):
            make_worker_request(request_id="x", messages=[{"role": "tool", "content": "bad"}], seed=1, max_new_tokens=1)

    def test_public_histories_reject_evaluator_metadata(self) -> None:
        with self.assertRaisesRegex(ValueError, "evaluator metadata"):
            serialize_agent_history("system", [{"role": "user", "content": "x", "gold_action": "hidden"}])
        with self.assertRaisesRegex(ValueError, "evaluator metadata"):
            serialize_user_history("system", [{"role": "user", "content": "x", "evaluator_outcome": "hidden"}])


if __name__ == "__main__":
    unittest.main()
