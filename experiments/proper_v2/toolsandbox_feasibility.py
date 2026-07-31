from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs" / "proper_v2" / "toolsandbox_feasibility.yaml"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    # JSON is a YAML subset; keeping this exploratory audit standard-library
    # only prevents it from modifying either the Qwen or ToolSandbox runtime.
    config = json.loads(path.read_text(encoding="utf-8"))
    if (
        config.get("status")
        != "exploratory_static_feasibility_before_toolsandbox_install_or_model_outputs"
    ):
        raise RuntimeError("ToolSandbox feasibility config has invalid status")
    return config


def function_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def literal_string(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def literal_strings(node: ast.AST | None) -> tuple[str, ...]:
    if not isinstance(node, (ast.List, ast.Tuple)):
        return ()
    values = [literal_string(item) for item in node.elts]
    return tuple(sorted(value for value in values if value is not None))


def attribute_names(node: ast.AST | None) -> tuple[str, ...]:
    if not isinstance(node, (ast.List, ast.Tuple)):
        return ()
    values = []
    for item in node.elts:
        if isinstance(item, ast.Attribute):
            values.append(item.attr)
        elif isinstance(item, ast.Name):
            values.append(item.id)
    return tuple(sorted(values))


def subscript_string(node: ast.AST | None) -> str | None:
    if not isinstance(node, ast.Subscript):
        return None
    return literal_string(node.slice)


def list_call_count(node: ast.AST | None, call_name: str) -> int:
    if not isinstance(node, (ast.List, ast.Tuple)):
        return 0
    return sum(
        isinstance(item, ast.Call) and function_name(item.func) == call_name
        for item in node.elts
    )


def list_length(node: ast.AST | None) -> int | None:
    if not isinstance(node, (ast.List, ast.Tuple)):
        return None
    return len(node.elts)


def keywords(call: ast.Call) -> dict[str, ast.AST]:
    return {
        str(item.arg): item.value
        for item in call.keywords
        if item.arg is not None
    }


def scenario_extensions(path: Path) -> list[dict[str, Any]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    records = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or function_name(node.func) != "ScenarioExtension":
            continue
        values = keywords(node)
        name = literal_string(values.get("name"))
        if name is None:
            continue
        tools = literal_strings(values.get("tool_allow_list"))
        categories = set(attribute_names(values.get("categories")))
        # This module appends the category to every extension after the
        # ScenarioExtension instances have been constructed.
        if path.name == "insufficient_information_scenarios.py":
            categories.add("INSUFFICIENT_INFORMATION")
        records.append(
            {
                "name": name,
                "source_file": path.relative_to(ROOT).as_posix(),
                "source_line": node.lineno,
                "base_scenario": subscript_string(values.get("base_scenario")),
                "tools": list(tools),
                "categories": sorted(categories),
                "milestone_count": list_call_count(
                    values.get("milestones"), "Milestone"
                ),
                "minefield_count": list_call_count(
                    values.get("minefields"), "Minefield"
                ),
                "explicit_milestone_edge_count": list_length(
                    values.get("milestone_edge_list")
                ),
                "explicit_minefield_edge_count": list_length(
                    values.get("minefield_edge_list")
                ),
            }
        )
    return records


def declared_python_311(pyproject: Path) -> bool:
    text = pyproject.read_text(encoding="utf-8")
    return '"Programming Language :: Python :: 3.11"' in text


def source_capabilities(repository: Path) -> dict[str, bool]:
    execution = (
        repository / "tool_sandbox" / "common" / "execution_context.py"
    ).read_text(encoding="utf-8")
    scenario = (
        repository / "tool_sandbox" / "common" / "scenario.py"
    ).read_text(encoding="utf-8")
    evaluation = (
        repository / "tool_sandbox" / "common" / "evaluation.py"
    ).read_text(encoding="utf-8")
    return {
        "snapshot_history_supported": (
            "self._database_history" in execution
            or "snapshot" in execution.lower()
        ),
        "milestone_dag_supported": (
            "milestone_edge_list" in scenario and "MilestoneMatcher" in evaluation
        ),
        "minefield_supported": (
            "minefield_edge_list" in scenario and "class Minefield" in evaluation
        ),
    }


def repository_revision(repository: Path) -> str:
    absolute = repository.resolve().as_posix()
    result = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={absolute}",
            "-C",
            str(repository),
            "rev-parse",
            "HEAD",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def paired_names(records: Iterable[Mapping[str, Any]]) -> list[dict[str, str]]:
    names = {str(item["name"]) for item in records}
    pairs = []
    for name in sorted(names):
        if not name.endswith("_implicit"):
            continue
        explicit = name.removesuffix("_implicit")
        if explicit in names:
            pairs.append({"explicit": explicit, "implicit": name})
    return pairs


def summarize(config: Mapping[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    excluded_tools = set(config["offline_exclusions"]["tools"])
    for record in records:
        record["requires_external_api"] = bool(
            set(record["tools"]) & excluded_tools
        )
        record["offline_eligible"] = not record["requires_external_api"]

    state = [
        item
        for item in records
        if "STATE_DEPENDENCY" in item["categories"] and item["offline_eligible"]
    ]
    insufficient = [
        item
        for item in records
        if "INSUFFICIENT_INFORMATION" in item["categories"]
        and item["offline_eligible"]
    ]
    state_tool_sets = {tuple(item["tools"]) for item in state}
    state_tools = {tool for item in state for tool in item["tools"]}
    pairs = paired_names(state)
    operation_capacity = {
        "invoke_prerequisite": len(state),
        "request_information_or_stop": len(insufficient),
        "switch_tool": 0,
        "use_fallback": 0,
    }
    return {
        "scenario_extension_count": len(records),
        "offline_scenario_extension_count": sum(
            item["offline_eligible"] for item in records
        ),
        "offline_state_dependency_count": len(state),
        "state_dependency_tool_set_count": len(state_tool_sets),
        "state_dependency_distinct_tool_count": len(state_tools),
        "state_dependency_tools": sorted(state_tools),
        "explicit_implicit_pair_count": len(pairs),
        "explicit_implicit_pairs": pairs,
        "offline_insufficient_information_count": len(insufficient),
        "operation_capacity": operation_capacity,
        "category_counts": dict(
            sorted(
                Counter(
                    category
                    for item in records
                    for category in item["categories"]
                ).items()
            )
        ),
    }


def run_audit(config_path: Path = CONFIG) -> dict[str, Any]:
    config = load_config(config_path)
    repository = ROOT / config["repository"]["local_directory"]
    if not repository.is_dir():
        raise FileNotFoundError(f"ToolSandbox repository is absent: {repository}")
    revision = repository_revision(repository)
    if revision != str(config["repository"]["revision"]):
        raise RuntimeError("ToolSandbox revision mismatch")
    scenario_root = repository / "tool_sandbox" / "scenarios"
    records = [
        record
        for path in sorted(scenario_root.glob("*_scenarios.py"))
        for record in scenario_extensions(path)
    ]
    if not records:
        raise RuntimeError("no statically declared ScenarioExtension records found")

    summary = summarize(config, records)
    capabilities = source_capabilities(repository)
    py311 = declared_python_311(repository / config["repository"]["pyproject"])
    gate = config["readiness_gate"]
    checks = {
        "state_dependency_capacity_met": summary[
            "offline_state_dependency_count"
        ]
        >= int(gate["minimum_offline_state_dependency_scenarios"]),
        "state_dependency_tool_set_diversity_met": summary[
            "state_dependency_tool_set_count"
        ]
        >= int(gate["minimum_state_dependency_tool_set_count"]),
        "state_dependency_tool_diversity_met": summary[
            "state_dependency_distinct_tool_count"
        ]
        >= int(gate["minimum_state_dependency_distinct_tool_count"]),
        "explicit_implicit_pair_capacity_met": summary[
            "explicit_implicit_pair_count"
        ]
        >= int(gate["minimum_explicit_implicit_pairs"]),
        "insufficient_information_capacity_met": summary[
            "offline_insufficient_information_count"
        ]
        >= int(gate["minimum_offline_insufficient_information_scenarios"]),
        "snapshot_history_supported": (
            capabilities["snapshot_history_supported"]
            if gate["require_snapshot_history"]
            else True
        ),
        "milestone_dag_supported": (
            capabilities["milestone_dag_supported"]
            if gate["require_milestone_dag"]
            else True
        ),
        "minefield_supported": (
            capabilities["minefield_supported"]
            if gate["require_minefield_support"]
            else True
        ),
        "python_311_declared": py311 if gate["require_python_311_declared"] else True,
    }
    native_cross_policy = (
        summary["operation_capacity"]["invoke_prerequisite"] > 0
        and summary["operation_capacity"]["request_information_or_stop"] > 0
    )
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_toolsandbox_static_feasibility_audit",
        "identities": {
            "config_sha256": sha256_file(config_path),
            "repository_revision": revision,
            "pyproject_sha256": sha256_file(
                repository / config["repository"]["pyproject"]
            ),
        },
        "boundary": {
            "static_source_only": True,
            "dependencies_installed": False,
            "external_api_called": False,
            "model_loaded": False,
            "model_outputs_read": False,
            "gpu_run_authorized": False,
        },
        "source_capabilities": capabilities,
        "python_311_declared": py311,
        "summary": summary,
        "readiness_checks": checks,
        "all_readiness_checks_met": all(checks.values()),
        "planning_decision": {
            "native_cross_policy_capacity_present": native_cross_policy,
            "native_switch_or_fallback_capacity_present": (
                summary["operation_capacity"]["switch_tool"] > 0
                or summary["operation_capacity"]["use_fallback"] > 0
            ),
            "next_action": (
                "isolated_install_and_dynamic_scenario_audit"
                if all(checks.values())
                else "stop_or_narrow_toolsandbox_scope"
            ),
        },
        "records": records,
        "interpretation_limits": {
            "static_scenario_count_is_not_selector_capacity": True,
            "static_scenario_count_is_not_model_effect_evidence": True,
            "policy_mapping_requires_dynamic_validation": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Statically audit ToolSandbox for PROPER v2 policy capacity."
    )
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    config = load_config(args.config)
    payload = run_audit(args.config)
    output = args.output or ROOT / config["output"]["path"]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "summary": payload["summary"],
                "source_capabilities": payload["source_capabilities"],
                "readiness_checks": payload["readiness_checks"],
                "planning_decision": payload["planning_decision"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    result = (
        "PASS_PROPER_V2_TOOLSANDBOX_STATIC_FEASIBILITY"
        if payload["all_readiness_checks_met"]
        else "STOP_PROPER_V2_TOOLSANDBOX_STATIC_FEASIBILITY"
    )
    print(f"RESULT={result}")
    print("NOTE=No dependency was installed, no external API was called, and no model was loaded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
