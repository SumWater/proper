from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONFIG = (
    ROOT / "configs" / "proper_v2" / "toolsandbox_dynamic_pilot.yaml"
)


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if (
        config.get("status")
        != "exploratory_mechanism_pilot_not_confirmatory_evidence"
    ):
        raise RuntimeError("ToolSandbox dynamic pilot config has invalid status")
    return config


def python_source_manifest(repository: Path) -> tuple[int, str]:
    files = sorted((repository / "tool_sandbox").rglob("*.py"))
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.relative_to(repository).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return len(files), digest.hexdigest()


def semantic_family(name: str) -> str:
    suffixes = ("_alt", "_implicit", "_multiple_user_turn")
    previous = None
    while previous != name:
        previous = name
        for suffix in suffixes:
            if name.endswith(suffix):
                name = name[: -len(suffix)]
    return name


def dynamic_inventory(config_path: Path = CONFIG) -> dict[str, Any]:
    config = load_config(config_path)
    repository = ROOT / config["repository"]["local_directory"]
    count, digest = python_source_manifest(repository)
    if count != int(config["repository"]["python_source_file_count"]):
        raise RuntimeError("ToolSandbox Python source file count mismatch")
    if digest != config["repository"]["python_source_manifest_sha256"]:
        raise RuntimeError("ToolSandbox Python source manifest mismatch")

    sys.path.insert(0, str(repository))
    try:
        from tool_sandbox.common.execution_context import (  # type: ignore
            DatabaseNamespace,
            ScenarioCategories,
        )
        from tool_sandbox.common.tool_discovery import ToolBackend  # type: ignore
        from tool_sandbox.scenarios import named_scenarios  # type: ignore
    except ImportError as error:
        raise RuntimeError(
            "ToolSandbox dependencies are unavailable; run this audit only "
            "inside its isolated Python environment"
        ) from error

    random.seed(0)
    scenarios = named_scenarios(preferred_tool_backend=ToolBackend.DEFAULT)
    exclusions = set(config["scenario_scope"]["external_tool_exclusions"])
    policy_categories = {
        getattr(ScenarioCategories, name)
        for name in config["scenario_scope"]["policy_categories"]
    }
    records: list[dict[str, Any]] = []
    for name, scenario in sorted(scenarios.items()):
        categories = set(scenario.categories)
        matched = sorted(
            category.name
            for category in categories & policy_categories
        )
        if (
            not matched
            or ScenarioCategories.NO_DISTRACTION_TOOLS not in categories
        ):
            continue
        tools = sorted(scenario.starting_context.tool_allow_list or [])
        if exclusions & set(tools):
            continue
        milestone_count = len(
            scenario.evaluation.milestone_matcher.milestones
        )
        minefield_count = len(
            scenario.evaluation.minefield_matcher.milestones
        )
        sandbox = scenario.starting_context.get_database(
            DatabaseNamespace.SANDBOX,
            drop_sandbox_message_index=False,
            get_all_history_snapshots=True,
        )
        records.append(
            {
                "name": name,
                "semantic_family": semantic_family(name),
                "policy_categories": matched,
                "tools": tools,
                "milestone_count": milestone_count,
                "minefield_count": minefield_count,
                "initial_snapshot_row_count": sandbox.height,
                "snapshot_capable": hasattr(
                    scenario.starting_context,
                    "get_most_recent_snapshot_sandbox_message_index",
                ),
            }
        )

    counts = Counter(
        category
        for record in records
        for category in record["policy_categories"]
    )
    families = {
        category: sorted(
            {
                record["semantic_family"]
                for record in records
                if category in record["policy_categories"]
            }
        )
        for category in config["scenario_scope"]["policy_categories"]
    }
    expected = config["scenario_scope"]["expected_offline_counts"]
    exact_counts = all(
        counts[category] == int(expected[category])
        for category in expected
    )
    gate = config["engineering_gate"]
    checks = {
        "exact_frozen_counts_met": exact_counts,
        "policy_type_count_met": len([value for value in counts.values() if value])
        >= int(gate["minimum_policy_type_count"]),
        "state_dependency_family_count_met": len(families["STATE_DEPENDENCY"])
        >= int(gate["minimum_state_dependency_family_count"]),
        "insufficient_information_family_count_met": len(
            families["INSUFFICIENT_INFORMATION"]
        )
        >= int(gate["minimum_insufficient_information_family_count"]),
        "evaluation_definition_present": all(
            record["milestone_count"] + record["minefield_count"] > 0
            for record in records
        ),
        "snapshot_capable_context_present": all(
            record["snapshot_capable"] for record in records
        ),
    }
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_toolsandbox_dynamic_inventory_pilot",
        "source_identity": {
            "revision": config["repository"]["revision"],
            "python_source_file_count": count,
            "python_source_manifest_sha256": digest,
        },
        "summary": {
            "scenario_count": len(records),
            "policy_counts": dict(sorted(counts.items())),
            "semantic_family_counts": {
                category: len(names) for category, names in families.items()
            },
            "semantic_families": families,
        },
        "engineering_checks": checks,
        "dynamic_inventory_ready": all(checks.values()),
        "boundary": dict(config["boundary"]),
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Dynamically inventory the narrow ToolSandbox pilot."
    )
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    config = load_config(args.config)
    result = dynamic_inventory(args.config)
    output = args.output or ROOT / config["output"]["path"]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "summary": result["summary"],
                "engineering_checks": result["engineering_checks"],
                "boundary": result["boundary"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    status = "PASS" if result["dynamic_inventory_ready"] else "STOP"
    print(f"RESULT={status}_PROPER_V2_TOOLSANDBOX_DYNAMIC_PILOT")
    print("NOTE=No scenario was played, no model was loaded, and no external API was called.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
