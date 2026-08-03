"""Lazy pinned-tau adapter for the acquisition runtime.

Importing this module never imports tau, model libraries, or a task runtime.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from typing import Any, Mapping, Sequence

from .acquisition_runtime import EnvironmentExecution
from .model_inventory import inventory_regular_files


def verify_frozen_model_directory(model_config: Mapping[str, Any]) -> dict[str, Any]:
    inventory = inventory_regular_files(Path(model_config["path"]), chunk_bytes=8388608)
    checks = {
        "manifest_sha256": inventory["manifest_sha256"] == model_config["content_manifest_sha256"],
        "file_count": inventory["file_count"] == model_config["inventory_file_count"],
        "total_bytes": inventory["total_bytes"] == model_config["inventory_total_bytes"],
    }
    if not all(checks.values()):
        raise RuntimeError(f"local model directory differs from frozen inventory: {checks}")
    return {"checks": checks, **inventory}


def install_pinned_tau_namespace(tau_source: Path) -> None:
    package_directory = tau_source / "tau2"
    if not package_directory.is_dir():
        raise RuntimeError(f"pinned tau source is absent: {package_directory}")
    if "tau2" in sys.modules:
        existing = sys.modules["tau2"]
        if list(getattr(existing, "__path__", [])) == [str(package_directory)]:
            return
        raise RuntimeError("tau2 was imported before the pinned-source namespace guard")
    package = types.ModuleType("tau2")
    package.__file__ = str(package_directory / "__init__.py")
    package.__package__ = "tau2"
    package.__path__ = [str(package_directory)]
    sys.modules["tau2"] = package


def normalize_public_tool_contracts(environment: Any) -> list[dict[str, Any]]:
    contracts: list[dict[str, Any]] = []
    for tool in sorted(environment.get_tools(), key=lambda item: item.name):
        function = tool.openai_schema["function"]
        contracts.append({
            "name": str(function["name"]),
            "description": str(function["description"]),
            "parameters": function["parameters"],
        })
    return contracts


class Tau3EnvironmentPort:
    def __init__(self, environment: Any) -> None:
        self.environment = environment

    def checkpoint(self) -> Mapping[str, Any]:
        tools = self.environment.tools
        if tools is None or tools.db is None:
            raise RuntimeError("tau assistant database is unavailable")
        return {"agent_data": tools.db.model_dump()}

    def execute(
        self, tool_name: str, arguments: Mapping[str, Any], effect_class: str
    ) -> EnvironmentExecution:
        from tau2.data_model.message import ToolCall

        response = self.environment.get_response(ToolCall(
            id="runtime-native-call", name=tool_name,
            arguments=dict(arguments), requestor="assistant",
        ))
        content: Any = response.content
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except json.JSONDecodeError:
                pass
        outcome = (
            "succeeded" if not response.error
            else "failed" if effect_class == "read_only"
            else "unknown"
        )
        return EnvironmentExecution(
            content=content, error=bool(response.error), outcome=outcome,
            native_executed=True,
        )


def build_pinned_tau_environment(
    *, root: Path, domain: str, raw_task: Mapping[str, Any]
) -> tuple[Tau3EnvironmentPort, str, Sequence[Mapping[str, Any]]]:
    if raw_task.get("initial_state") is not None:
        raise RuntimeError("frozen acquisition tasks require null initial_state")
    tau_source = root / "external/tau2-bench/src"
    install_pinned_tau_namespace(tau_source)
    if domain == "airline":
        from tau2.domains.airline.environment import get_environment
    elif domain == "retail":
        from tau2.domains.retail.environment import get_environment
    else:
        raise ValueError(f"unsupported acquisition domain: {domain}")
    environment = get_environment()
    return Tau3EnvironmentPort(environment), environment.get_policy(), normalize_public_tool_contracts(environment)
