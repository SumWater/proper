"""Read-only, no-model qualification of a frozen PlanBench-XL checkout."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = (
    ROOT / "configs/proper_v2_3/planbench_xl_source_qualification_v2_3.json"
)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_revision(source_root: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(source_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _generate_blocker_plan(
    source_root: Path, config: Mapping[str, Any], output_path: Path
) -> None:
    data = source_root / "src/data/retail"
    policy = config["structural_blocker_plan"]
    command = [
        sys.executable,
        str(source_root / "src/env/events/blocker.py"),
        "--paths_set_catalog",
        str(data / "paths_set_catalog.json"),
        "--baseline_tools",
        str(data / "baseline_tools.json"),
        "--tasks",
        str(data / "tasks.json"),
        "--output",
        str(output_path),
        "--selection_mode",
        policy["selection_mode"],
        "--target_remaining_ratio",
        str(policy["target_remaining_ratio"]),
        "--min_remaining_paths",
        str(policy["min_remaining_paths"]),
        "--remaining_tolerance",
        str(policy["remaining_tolerance"]),
        "--remaining_path_length_objective",
        policy["remaining_path_length_objective"],
        "--blocking_edge_count_objective",
        policy["blocking_edge_count_objective"],
        "--seed",
        str(policy["seed"]),
        "--noise_mode",
        policy["noise_mode"],
        "--fixed_noise_type",
        policy["fixed_noise_type"],
        "--max_combo_candidates",
        str(policy["max_combo_candidates"]),
        "--max_cover_size",
        str(policy["max_cover_size"]),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)


def qualify_source(
    source_root: Path, config_path: Path = DEFAULT_CONFIG
) -> dict[str, Any]:
    source_root = source_root.resolve()
    config = _load(config_path)
    expected = config["expected_inventory"]
    frozen_files = config["frozen_files"]
    actual_hashes = {
        relative: _sha256(source_root / relative) for relative in frozen_files
    }
    revision = _git_revision(source_root)
    data_root = source_root / "src/data/retail"
    datatypes = _load(data_root / "datatypes.json")
    baseline = _load(data_root / "baseline_tools.json")
    noisy = _load(data_root / "noisy_tools.json")
    blockers = _load(data_root / "blocker_tools.json")
    tasks = _load(data_root / "tasks.json")
    queries = _load(data_root / "queries.json")
    paths = _load(data_root / "paths_set_catalog.json")

    noise_counts = collections.Counter(item.get("noise_type") for item in blockers)
    task_steps = [int(item["steps"]) for item in tasks]
    tool_total = len(baseline) + len(noisy) + len(blockers)
    license_files = sorted(
        item.name
        for item in source_root.iterdir()
        if item.is_file()
        and ("license" in item.name.lower() or "copying" in item.name.lower())
    )

    with tempfile.TemporaryDirectory(prefix="proper-planbench-xl-audit-") as tmp:
        plan_path = Path(tmp) / "explicit_blocker_plan.json"
        _generate_blocker_plan(source_root, config, plan_path)
        plan_hash = _sha256(plan_path)
        plan = _load(plan_path)

    plan_tasks = plan["tasks"]
    successful = [item for item in plan_tasks if item.get("status") == "success"]
    nonempty = [
        item for item in successful if item["meta"]["selected_edge_count"] > 0
    ]
    zero_edge = [
        item for item in successful if item["meta"]["selected_edge_count"] == 0
    ]
    remaining_steps = [
        step
        for item in successful
        for step in item["meta"]["actual_remaining_path_steps"]
    ]

    checks = {
        "frozen_revision_matches": revision == config["source"]["revision"],
        "all_frozen_file_hashes_match": actual_hashes == frozen_files,
        "query_and_task_counts_match": len(queries)
        == len(tasks)
        == expected["query_count"]
        == expected["task_count"],
        "query_task_ids_match": {item["task_id"] for item in queries}
        == {item["task_id"] for item in tasks},
        "datatype_count_matches": len(datatypes) == expected["datatype_count"],
        "tool_counts_match": (
            len(baseline) == expected["baseline_tool_count"]
            and len(noisy) == expected["noisy_tool_count"]
            and len(blockers) == expected["blocker_tool_count"]
            and tool_total == expected["total_tool_count"]
        ),
        "task_step_range_matches": min(task_steps) == expected["minimum_task_steps"]
        and max(task_steps) == expected["maximum_task_steps"],
        "all_path_catalog_tasks_present": set(paths)
        == {item["task_id"] for item in tasks},
        "three_blocker_families_cover_all_baseline_tools": set(noise_counts)
        == {"explicit failures", "implicit failures", "semantic misleading"}
        and all(
            count == expected["blocker_count_per_noise_type"]
            for count in noise_counts.values()
        ),
        "structural_plan_hash_matches": plan_hash
        == config["structural_blocker_plan"]["expected_plan_sha256"],
        "all_task_plans_succeed": len(successful)
        == config["structural_blocker_plan"]["expected_successful_task_plans"],
        "nonempty_failure_plan_count_matches": len(nonempty)
        == config["structural_blocker_plan"]["expected_nonempty_failure_plans"],
        "zero_edge_plan_count_matches": len(zero_edge)
        == config["structural_blocker_plan"]["expected_zero_edge_plans"],
        "remaining_paths_are_long_horizon": min(remaining_steps)
        >= config["structural_blocker_plan"]["expected_minimum_remaining_steps"],
        "license_absence_matches_frozen_observation": not license_files
        and config["source"]["license_file_present"] is False,
        "effect_coverage_is_read_only_only": (
            config["effect_coverage_interpretation"]["read_only_tool_count"]
            == len(baseline)
            and config["effect_coverage_interpretation"]
            ["idempotent_state_setting_tool_count"]
            == 0
            and config["effect_coverage_interpretation"]
            ["non_idempotent_side_effect_tool_count"]
            == 0
        ),
        "no_model_or_gpu_authority": all(
            config["boundary"][key] is False
            for key in (
                "model_loaded",
                "model_outputs_read",
                "target_scenarios_played",
                "gpu_run_authorized",
                "confirmatory_claim_authorized",
            )
        ),
    }
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_3_planbench_xl_source_qualification",
        "source_revision": revision,
        "source_file_sha256": actual_hashes,
        "checks": checks,
        "passed": all(checks.values()),
        "inventory": {
            "query_count": len(queries),
            "task_count": len(tasks),
            "datatype_count": len(datatypes),
            "baseline_tool_count": len(baseline),
            "noisy_tool_count": len(noisy),
            "blocker_tool_count": len(blockers),
            "total_tool_count": tool_total,
            "minimum_task_steps": min(task_steps),
            "maximum_task_steps": max(task_steps),
            "blocker_count_by_noise_type": dict(sorted(noise_counts.items())),
        },
        "structural_blocker_plan": {
            "sha256": plan_hash,
            "successful_task_plan_count": len(successful),
            "nonempty_failure_plan_count": len(nonempty),
            "zero_edge_plan_count": len(zero_edge),
            "minimum_remaining_path_steps": min(remaining_steps),
        },
        "action_effect_coverage": {
            "read_only": len(baseline),
            "idempotent_state_setting": 0,
            "non_idempotent_side_effect": 0,
            "unknown_effect": 0,
        },
        "license_files": license_files,
        "structural_continuation_pool_size": len(nonempty),
        "accepted_full_proper_v2_3_candidate_count": 0,
        "model_loaded": False,
        "model_outputs_read": False,
        "gpu_used": False,
        "model_run_authorized": False,
        "confirmatory_run_authorized": False,
        "disposition": "stop_full_proper_v2_3_capacity_gate",
        "stop_reasons": [
            "zero_state_setting_or_non_idempotent_side_effect_coverage",
            "base_model_capability_not_established",
            "source_redistribution_license_not_present",
        ],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = qualify_source(args.source_root, args.config)
    if args.output is not None:
        output = args.output.resolve()
        allowed_root = (ROOT / "outputs/proper_v2_3").resolve()
        if not output.is_relative_to(allowed_root):
            raise ValueError("output must remain under outputs/proper_v2_3")
        if output.exists():
            raise FileExistsError(f"refusing to overwrite qualification output: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
