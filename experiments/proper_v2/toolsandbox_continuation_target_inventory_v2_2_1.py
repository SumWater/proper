from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
CONFIG = (
    ROOT
    / "configs"
    / "proper_v2"
    / "toolsandbox_continuation_target_inventory_v2_2_1.yaml"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    suffixes = (
        "_alt",
        "_implicit",
        "_multiple_user_turn",
        "_three_distraction_tools",
        "_ten_distraction_tools",
        "_all_tools",
        "_tool_name_scrambled",
        "_tool_description_scrambled",
        "_arg_name_scrambled",
        "_arg_description_scrambled",
        "_arg_type_scrambled",
    )
    previous = None
    while previous != name:
        previous = name
        for suffix in suffixes:
            if name.endswith(suffix):
                name = name[: -len(suffix)]
    return name


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("status") != (
        "prospective_continuation_target_inventory_before_new_model_outputs"
    ):
        raise RuntimeError("continuation target inventory status is invalid")
    boundary = config["boundary"]
    if (
        not boundary["inventory_only"]
        or boundary["scenario_played"]
        or boundary["model_loaded"]
        or boundary["model_outputs_read"]
        or boundary["gpu_run_authorized"]
        or boundary["confirmatory_claim_authorized"]
    ):
        raise RuntimeError("continuation target inventory boundary is invalid")
    for item in config["frozen_inputs"].values():
        target = ROOT / str(item["path"])
        observed = sha256_file(target)
        if observed != str(item["sha256"]):
            raise RuntimeError(
                f"target inventory input mismatch: {target}; "
                f"expected={item['sha256']} observed={observed}"
            )
    return config


def inventory(config_path: Path = CONFIG) -> dict[str, Any]:
    config = load_config(config_path)
    repository = ROOT / str(config["repository"]["local_directory"])
    count, digest = python_source_manifest(repository)
    if count != int(config["repository"]["python_source_file_count"]):
        raise RuntimeError("ToolSandbox Python source file count mismatch")
    if digest != str(config["repository"]["python_source_manifest_sha256"]):
        raise RuntimeError("ToolSandbox Python source identity mismatch")

    sys.path.insert(0, str(repository))
    try:
        from tool_sandbox.common.execution_context import (  # type: ignore
            ScenarioCategories,
        )
        from tool_sandbox.common.tool_discovery import ToolBackend  # type: ignore
        from tool_sandbox.scenarios import named_scenarios  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "ToolSandbox dependencies are unavailable; run inside "
            "proper-toolsandbox"
        ) from exc

    manifest_item = config["frozen_inputs"]["v2_1_prepared_manifest"]
    prepared = json.loads(
        (ROOT / str(manifest_item["path"])).read_text(encoding="utf-8")
    )
    exposed_names = {
        str(item["scenario_name"]) for item in prepared["records"]
    }
    exposed_families = {
        semantic_family(name) for name in exposed_names
    }
    screen = config["eligibility_screen"]
    required_categories = {
        getattr(ScenarioCategories, str(name))
        for name in screen["required_categories"]
    }
    exclusions = set(str(name) for name in screen["external_tool_exclusions"])
    protected_families = set(
        str(name) for name in screen["protected_memory_source_families"]
    )
    minimum_milestones = int(screen["minimum_milestone_count"])

    random.seed(0)
    scenarios = named_scenarios(preferred_tool_backend=ToolBackend.DEFAULT)
    records = []
    for name, scenario in sorted(scenarios.items()):
        family = semantic_family(str(name))
        categories = set(scenario.categories)
        tools = sorted(scenario.starting_context.tool_allow_list or [])
        milestone_count = len(
            scenario.evaluation.milestone_matcher.milestones
        )
        minefield_count = len(
            scenario.evaluation.minefield_matcher.milestones
        )
        reason_codes = []
        if str(name) in exposed_names:
            disposition = "exclude_model_exposed_target"
            reason_codes.append("exact_target_was_model_exposed")
        elif (
            bool(screen["exclude_model_exposed_semantic_families"])
            and family in exposed_families
        ):
            disposition = "exclude_model_exposed_family_variant"
            reason_codes.append("semantic_family_was_model_exposed")
        elif family in protected_families:
            disposition = "exclude_memory_source_family"
            reason_codes.append("protected_memory_source_family")
        elif not required_categories.issubset(categories):
            disposition = "exclude_missing_required_categories"
            reason_codes.append("required_category_set_not_satisfied")
        elif exclusions & set(tools):
            disposition = "exclude_external_tool_dependency"
            reason_codes.append("external_tool_dependency")
        elif milestone_count < minimum_milestones:
            disposition = "exclude_insufficient_continuation_depth"
            reason_codes.append("fewer_than_three_native_milestones")
        else:
            disposition = "requires_cpu_selector_and_branch_screening"
            reason_codes.extend(
                (
                    "inventory_capacity_only",
                    "selector_effect_not_yet_established",
                    "recoverable_branch_not_yet_verified",
                )
            )
        records.append(
            {
                "scenario_name": str(name),
                "semantic_family": family,
                "categories": sorted(category.name for category in categories),
                "tools": tools,
                "milestone_count": milestone_count,
                "minefield_count": minefield_count,
                "minimum_steps_after_prerequisite_proxy": max(
                    0,
                    milestone_count - 1,
                ),
                "disposition": disposition,
                "reason_codes": sorted(reason_codes),
            }
        )
    counts = Counter(item["disposition"] for item in records)
    candidates = [
        item
        for item in records
        if item["disposition"]
        == "requires_cpu_selector_and_branch_screening"
    ]
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_2_1_continuation_target_inventory",
        "identities": {
            "config_sha256": sha256_file(config_path),
            "toolsandbox_revision": config["repository"]["revision"],
            "toolsandbox_python_source_sha256": digest,
            "v2_1_prepared_manifest_sha256": manifest_item["sha256"],
        },
        "summary": {
            "all_named_scenario_count": len(records),
            "disposition_counts": dict(sorted(counts.items())),
            "candidate_count": len(candidates),
            "candidate_semantic_family_count": len(
                {item["semantic_family"] for item in candidates}
            ),
            "model_run_authorized": False,
            "confirmatory_ready": False,
        },
        "candidate_names": [
            item["scenario_name"] for item in candidates
        ],
        "records": records,
        "next_gate": dict(config["next_gate"]),
        "boundary": dict(config["boundary"]),
        "interpretation_limits": {
            "scenario_metadata_inspected_without_play": True,
            "milestone_count_is_only_a_depth_proxy": True,
            "candidate_requires_cpu_selector_screen": True,
            "candidate_requires_recoverable_branch_verification": True,
            "inventory_alone_does_not_create_heldout_targets": True,
        },
    }


def write_result(
    result: Mapping[str, Any],
    config: Mapping[str, Any],
) -> Path:
    output = ROOT / str(config["output"]["path"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inventory prospective continuation targets without playing them."
    )
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()
    config = load_config(args.config)
    result = inventory(args.config)
    output = write_result(result, config)
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2, sort_keys=True))
    print(f"OUTPUT={output}")
    print("RESULT=PASS_CONTINUATION_TARGET_INVENTORY_V2_2_1")
    print(
        "NOTE=No scenario was played and inventory candidates are not "
        "model-run-authorized."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
