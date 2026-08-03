"""Scripted JSONL participant used only by the no-model acquisition dry-run."""

from __future__ import annotations

import json
import sys
from typing import Any, Mapping


def scripted_raw_text(request_id: str) -> str:
    parts = request_id.split(":")
    if len(parts) != 3 or not parts[0].startswith("attempt-"):
        raise ValueError("unexpected synthetic request id")
    attempt = int(parts[0].split("-")[1])
    participant, ordinal = parts[1], int(parts[2])
    if participant == "user":
        return json.dumps({"kind":"message","content":f"synthetic request {attempt}"}, separators=(",", ":"))
    if attempt == 2:
        return '{"kind":"tool","tool_name":"set_value","arguments":{"value":2}}'
    if attempt == 3:
        return '{"kind":"tool","tool_name":"send_value","arguments":{"value":3}}'
    if attempt == 4:
        return "not-json"
    if attempt in {6, 7}:
        return '{"kind":"tool","tool_name":"set_value","arguments":{"value":7}}'
    return json.dumps({"kind":"message","content":f"synthetic agent message {ordinal}"}, separators=(",", ":"))


def response(request: Mapping[str, Any]) -> dict[str, Any]:
    request_id = str(request["request_id"])
    if request_id.startswith("attempt-05:"):
        return {
            "request_id": request_id, "ok": False,
            "error": "SyntheticWorkerError: deliberate fixture",
            "synthetic_non_model_output": True,
        }
    return {
        "request_id": request_id,
        "ok": True,
        "raw_text": scripted_raw_text(request_id),
        "usage": {"prompt_token_count":7,"completion_token_count":5},
        "synthetic_non_model_output": True,
    }


def main() -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
            payload = response(request)
        except Exception as exc:
            payload = {
                "request_id": None, "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "synthetic_non_model_output": True,
            }
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
