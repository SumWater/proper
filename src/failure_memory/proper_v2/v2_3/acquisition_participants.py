"""CPU-contract layer between public tau messages and the local Qwen worker."""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

FORBIDDEN_AGENT_KEYS = frozenset(
    {"task_id", "source_task_id", "evaluation_criteria", "gold_action", "gold_actions", "recoverability", "evaluator_outcome", "private_user_scenario"}
)
WORKER_ROLES = frozenset({"system", "user", "assistant"})


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _forbidden_paths(value: Any, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if str(key).casefold() in FORBIDDEN_AGENT_KEYS:
                found.append(child_path)
            found.extend(_forbidden_paths(child, child_path))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            found.extend(_forbidden_paths(child, f"{path}[{index}]"))
    return found


def render_agent_system_prompt(
    prompt_config: Mapping[str, Any],
    *,
    public_policy: str,
    public_tools: Sequence[Mapping[str, Any]],
) -> str:
    if not public_policy.strip() or not public_tools:
        raise ValueError("agent prompt requires public policy and tools")
    forbidden = _forbidden_paths(public_tools)
    if forbidden:
        raise ValueError(f"agent tool contracts contain evaluator metadata: {forbidden}")
    agent = prompt_config["agent"]
    return "\n\n".join(
        (
            str(agent["instruction"]),
            f"<{agent['policy_tag']}>\n{public_policy.strip()}\n</{agent['policy_tag']}>",
            f"<{agent['tools_tag']}>\n{canonical_json(list(public_tools))}\n</{agent['tools_tag']}>",
            str(agent["output_contract"]),
        )
    )


def render_user_system_prompt(
    prompt_config: Mapping[str, Any],
    *,
    simulation_guidelines: str,
    private_scenario: str,
) -> str:
    if not simulation_guidelines.strip() or not private_scenario.strip():
        raise ValueError("user prompt requires guidelines and scenario")
    user = prompt_config["user"]
    return "\n\n".join(
        (
            str(user["instruction"]),
            f"<{user['guidelines_tag']}>\n{simulation_guidelines.strip()}\n</{user['guidelines_tag']}>",
            f"<{user['scenario_tag']}>\n{private_scenario.strip()}\n</{user['scenario_tag']}>",
            str(user["output_contract"]),
        )
    )


def _public_call_payload(message: Mapping[str, Any]) -> str:
    return canonical_json({"tag": "public_tool_call", "tool_calls": message.get("tool_calls") or []})


def _public_result_payload(message: Mapping[str, Any]) -> str:
    return canonical_json(
        {
            "tag": "public_tool_result",
            "tool_call_id": message.get("tool_call_id"),
            "content": message.get("content"),
            "error": bool(message.get("error", False)),
        }
    )


def serialize_agent_history(
    system_prompt: str, public_history: Sequence[Mapping[str, Any]]
) -> list[dict[str, str]]:
    forbidden = _forbidden_paths(public_history)
    if forbidden:
        raise ValueError(f"agent history contains evaluator metadata: {forbidden}")
    messages = [{"role": "system", "content": system_prompt}]
    for message in public_history:
        role = message.get("role")
        if role == "user":
            content = str(message.get("content") or "").strip()
            worker_role = "user"
        elif role == "assistant":
            content = (
                _public_call_payload(message)
                if message.get("tool_calls")
                else str(message.get("content") or "").strip()
            )
            worker_role = "assistant"
        elif role == "tool":
            content = _public_result_payload(message)
            worker_role = "user"
        else:
            raise ValueError(f"unsupported public agent-history role: {role}")
        if not content:
            raise ValueError("participant history messages must be non-empty")
        messages.append({"role": worker_role, "content": content})
    return messages


def serialize_user_history(
    system_prompt: str, public_history: Sequence[Mapping[str, Any]]
) -> list[dict[str, str]]:
    forbidden = _forbidden_paths(public_history)
    if forbidden:
        raise ValueError(f"user public history contains evaluator metadata: {forbidden}")
    messages = [{"role": "system", "content": system_prompt}]
    for message in public_history:
        role = message.get("role")
        if role == "assistant":
            content = _public_call_payload(message) if message.get("tool_calls") else str(message.get("content") or "").strip()
            worker_role = "user"
        elif role == "user":
            content = str(message.get("content") or "").strip()
            worker_role = "assistant"
        elif role == "tool":
            content = _public_result_payload(message)
            worker_role = "user" if message.get("requestor", "assistant") == "assistant" else "assistant"
        else:
            raise ValueError(f"unsupported public user-history role: {role}")
        if not content:
            raise ValueError("participant history messages must be non-empty")
        messages.append({"role": worker_role, "content": content})
    return messages


def make_worker_request(
    *, request_id: str, messages: Sequence[Mapping[str, str]], seed: int, max_new_tokens: int
) -> dict[str, Any]:
    if not request_id or seed < 0 or max_new_tokens <= 0:
        raise ValueError("invalid deterministic worker request")
    normalized = []
    for message in messages:
        role, content = str(message["role"]), str(message["content"])
        if role not in WORKER_ROLES or not content.strip():
            raise ValueError("worker messages require supported roles and non-empty content")
        normalized.append({"role": role, "content": content})
    return {"request_id": request_id, "messages": normalized, "seed": seed, "max_new_tokens": max_new_tokens}


def _strict_object(raw_text: str) -> dict[str, Any]:
    try:
        value = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError("participant output must be one strict JSON object") from exc
    if not isinstance(value, dict):
        raise ValueError("participant output must be a JSON object")
    return value


def _matches_public_schema(value: Any, schema: Mapping[str, Any]) -> bool:
    if "enum" in schema and value not in schema["enum"]:
        return False
    if "anyOf" in schema:
        return any(_matches_public_schema(value, option) for option in schema["anyOf"])
    expected = schema.get("type")
    if isinstance(expected, list):
        return any(_matches_public_schema(value, {**schema, "type": item}) for item in expected)
    if expected == "null":
        return value is None
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "string":
        return isinstance(value, str)
    if expected == "array":
        return isinstance(value, list) and all(
            _matches_public_schema(item, schema.get("items") or {}) for item in value
        )
    if expected == "object":
        if not isinstance(value, Mapping):
            return False
        properties = schema.get("properties") or {}
        required = set(schema.get("required") or [])
        if not required.issubset(value):
            return False
        if schema.get("additionalProperties") is False and not set(value).issubset(properties):
            return False
        return all(
            key not in properties or _matches_public_schema(child, properties[key])
            for key, child in value.items()
        )
    return True


def _validate_arguments(arguments: Mapping[str, Any], tool: Mapping[str, Any]) -> None:
    parameters = tool.get("parameters") or {}
    required = set(parameters.get("required") or [])
    properties = set((parameters.get("properties") or {}).keys())
    keys = set(arguments)
    if not required.issubset(keys):
        raise ValueError(f"missing required public tool arguments: {sorted(required - keys)}")
    if parameters.get("additionalProperties") is False and not keys.issubset(properties):
        raise ValueError(f"unknown public tool arguments: {sorted(keys - properties)}")
    if not _matches_public_schema(arguments, parameters):
        raise ValueError("public tool arguments violate the public JSON schema")


def parse_agent_output(raw_text: str, public_tools: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    value = _strict_object(raw_text)
    if value.get("kind") == "message" and set(value) == {"kind", "content"}:
        content = value.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("agent message content must be non-empty")
        return {"kind": "message", "content": content.strip()}
    if value.get("kind") == "tool" and set(value) == {"kind", "tool_name", "arguments"}:
        registry = {str(tool["name"]): tool for tool in public_tools}
        name, arguments = value.get("tool_name"), value.get("arguments")
        if name not in registry or not isinstance(arguments, Mapping):
            raise ValueError("agent requested an unknown tool or invalid arguments")
        _validate_arguments(arguments, registry[str(name)])
        return {"kind": "tool", "tool_name": str(name), "arguments": dict(arguments)}
    raise ValueError("agent output violates the exclusive message-or-tool contract")


def parse_user_output(raw_text: str) -> dict[str, str]:
    value = _strict_object(raw_text)
    if value.get("kind") != "message" or set(value) != {"kind", "content"}:
        raise ValueError("user output must contain exactly kind=message and content")
    content = value.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("user message content must be non-empty")
    return {"kind": "message", "content": content.strip()}
