"""Statically qualify the pinned tau3-bench source for a later CPU branch screen.

This audit reads only the explicitly hashed task, split, policy, and tool files.
It never imports tau3-bench, executes a task, or opens bundled trajectories and
results.  Evaluator action specifications are used only as audit-side
continuation-depth proxies and are never passed to the PROPER method.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = (
    ROOT / "configs" / "proper_v2_3" / "tau3_source_qualification_v2_3.yaml"
)
DEFAULT_OUTPUT = (
    ROOT
    / "outputs"
    / "proper_v2_3"
    / "tau3_source_qualification"
    / "audit.json"
)

EFFECT_CLASSES = (
    "read_only",
    "idempotent_state_setting",
    "non_idempotent_side_effect",
)


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _load_list(path: Path) -> list[Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError(f"expected JSON array: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _git(repository: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def _decorated_tool_types(path: Path) -> dict[str, str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    tools: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or not decorator.args:
                continue
            if (
                not isinstance(decorator.func, ast.Name)
                or decorator.func.id != "is_tool"
            ):
                continue
            argument = decorator.args[0]
            if (
                isinstance(argument, ast.Attribute)
                and isinstance(argument.value, ast.Name)
                and argument.value.id == "ToolType"
            ):
                tools[node.name] = argument.attr
    return tools


def _effect_lookup(domain_contracts: Mapping[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for effect in EFFECT_CLASSES:
        names = domain_contracts.get(effect)
        if not isinstance(names, list):
            raise ValueError(f"action effect contract {effect} must be an array")
        for name in names:
            normalized = str(name)
            if normalized in result:
                raise ValueError(f"duplicate action effect contract: {normalized}")
            result[normalized] = effect
    return result


def _prospective_partition(
    *, domain: str, task_id: str, source_split: str, config: Mapping[str, Any]
) -> str:
    partition = config["prospective_partition"]
    if source_split == partition["development_source_split"]:
        return "development"
    if source_split != partition["future_evaluation_source_split"]:
        raise ValueError(f"unexpected upstream split: {source_split}")
    labels = partition["future_evaluation_labels"]
    digest = hashlib.sha256(
        f"{partition['future_evaluation_seed']}:{domain}:{task_id}".encode("utf-8")
    ).digest()
    return str(labels[digest[0] % len(labels)])


def _task_and_opportunity_audit(
    source: Path, config: Mapping[str, Any]
) -> tuple[dict[str, Any], list[dict[str, str]], Counter[str]]:
    summaries: dict[str, Any] = {}
    partition_records: list[dict[str, str]] = []
    total_opportunities: Counter[str] = Counter()

    for domain, domain_config in config["domains"].items():
        tasks = _load_list(source / domain_config["task_file"])
        split_payload = _load_object(source / domain_config["split_file"])
        task_by_id: dict[str, Mapping[str, Any]] = {}
        for task in tasks:
            if not isinstance(task, Mapping):
                raise ValueError(f"{domain} task is not an object")
            task_id = str(task.get("id"))
            if task_id in task_by_id:
                raise ValueError(f"duplicate {domain} task id: {task_id}")
            task_by_id[task_id] = task

        split_ids = {
            name: [str(value) for value in values]
            for name, values in split_payload.items()
            if isinstance(values, list)
        }
        base = split_ids[domain_config["eligible_pool_split"]]
        train = split_ids["train"]
        test = split_ids["test"]
        if set(train) & set(test):
            raise ValueError(f"{domain} upstream train/test overlap")
        if not set(train).issubset(base) or not set(test).issubset(base):
            raise ValueError(f"{domain} train/test is outside eligible base pool")
        if len(base) != len(set(base)):
            raise ValueError(f"{domain} base split contains duplicate ids")
        if not set(base).issubset(task_by_id):
            raise ValueError(f"{domain} base split references missing tasks")

        source_split_by_id = {task_id: "train" for task_id in train}
        source_split_by_id.update({task_id: "test" for task_id in test})
        if set(source_split_by_id) != set(base):
            raise ValueError(f"{domain} base split is not exactly train plus test")

        effect_by_action = _effect_lookup(config["action_effect_contracts"][domain])
        domain_opportunities: Counter[str] = Counter()
        uncovered_actions: Counter[str] = Counter()
        partition_counts: Counter[str] = Counter()

        for task_id in base:
            source_split = source_split_by_id[task_id]
            target_partition = _prospective_partition(
                domain=domain,
                task_id=task_id,
                source_split=source_split,
                config=config,
            )
            partition_counts[target_partition] += 1
            partition_records.append(
                {
                    "domain": domain,
                    "task_id": task_id,
                    "partition": target_partition,
                }
            )

            task = task_by_id[task_id]
            criteria = task.get("evaluation_criteria")
            if not isinstance(criteria, Mapping):
                raise ValueError(f"{domain}/{task_id} lacks evaluation criteria")
            actions = criteria.get("actions")
            if not isinstance(actions, list):
                raise ValueError(f"{domain}/{task_id} action proxy is not an array")
            for index, action in enumerate(actions):
                if not isinstance(action, Mapping):
                    raise ValueError(
                        f"{domain}/{task_id} action proxy is not an object"
                    )
                requestor = str(action.get("requestor", "assistant"))
                if requestor != "assistant":
                    continue
                name = str(action.get("name", ""))
                effect = effect_by_action.get(name)
                if effect is None:
                    uncovered_actions[name] += 1
                    continue
                if len(actions) - index - 1 >= 2:
                    domain_opportunities[effect] += 1
                    total_opportunities[effect] += 1

        summaries[domain] = {
            "source_task_count": len(tasks),
            "eligible_base_task_count": len(base),
            "upstream_train_count": len(train),
            "upstream_test_count": len(test),
            "prospective_partition_counts": dict(sorted(partition_counts.items())),
            "static_continuation_opportunities": {
                effect: domain_opportunities[effect] for effect in EFFECT_CLASSES
            },
            "uncovered_assistant_action_names": dict(sorted(uncovered_actions.items())),
        }

    return summaries, partition_records, total_opportunities


def qualify_source(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = _load_object(config_path)
    source = ROOT / config["repository"]["local_directory"]
    if not source.is_dir():
        raise FileNotFoundError(f"pinned tau3-bench checkout is absent: {source}")

    selected_inputs = config["selected_inputs"]
    forbidden = tuple(
        PurePosixPath(value) for value in config["forbidden_source_paths"]
    )
    hash_records: list[dict[str, Any]] = []
    forbidden_selected: list[str] = []
    for item in selected_inputs:
        relative = PurePosixPath(item["path"])
        if any(
            relative == prefix or prefix in relative.parents for prefix in forbidden
        ):
            forbidden_selected.append(relative.as_posix())
        path = source.joinpath(*relative.parts)
        hash_records.append(
            {
                "path": relative.as_posix(),
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
                "expected_sha256": item["sha256"],
                "expected_bytes": item["bytes"],
            }
        )

    source_hashes_match = all(
        record["sha256"] == record["expected_sha256"]
        and record["bytes"] == record["expected_bytes"]
        for record in hash_records
    )
    source_manifest = [
        {
            "path": record["path"],
            "sha256": record["sha256"],
            "bytes": record["bytes"],
        }
        for record in hash_records
    ]

    tool_checks: dict[str, Any] = {}
    all_contracts_resolve = True
    for domain in config["domains"]:
        tool_path = source / f"src/tau2/domains/{domain}/tools.py"
        declared = _decorated_tool_types(tool_path)
        contracts = _effect_lookup(config["action_effect_contracts"][domain])
        missing = sorted(set(contracts) - set(declared))
        read_mismatches = sorted(
            name
            for name, effect in contracts.items()
            if effect == "read_only"
            and declared.get(name) not in {"READ", "GENERIC"}
        )
        mutation_mismatches = sorted(
            name
            for name, effect in contracts.items()
            if effect != "read_only"
            and declared.get(name) not in {"WRITE", "GENERIC"}
        )
        passed = not missing and not read_mismatches and not mutation_mismatches
        all_contracts_resolve &= passed
        tool_checks[domain] = {
            "decorated_public_tool_count": len(declared),
            "contracted_tool_count": len(contracts),
            "missing_contract_tools": missing,
            "read_type_mismatches": read_mismatches,
            "mutation_type_mismatches": mutation_mismatches,
            "passed": passed,
        }

    domain_summaries, partition_records, opportunities = _task_and_opportunity_audit(
        source, config
    )
    domain_counts_match = all(
        summary["source_task_count"]
        == config["domains"][domain]["source_task_count"]
        and summary["eligible_base_task_count"]
        == config["domains"][domain]["eligible_pool_count"]
        and summary["upstream_train_count"]
        == config["domains"][domain]["upstream_train_count"]
        and summary["upstream_test_count"]
        == config["domains"][domain]["upstream_test_count"]
        for domain, summary in domain_summaries.items()
    )
    no_uncovered_actions = all(
        not summary["uncovered_assistant_action_names"]
        for summary in domain_summaries.values()
    )
    gates = config["source_gates"]
    total_count = sum(opportunities.values())
    capacity_checks = {
        "independent_domain_gate": len(domain_summaries)
        >= gates["minimum_independent_domains"],
        "static_continuation_gate": total_count
        >= gates["minimum_static_continuation_opportunities"],
        "non_idempotent_gate": opportunities["non_idempotent_side_effect"]
        >= gates["minimum_non_idempotent_opportunities"],
        "idempotent_state_setting_gate": opportunities["idempotent_state_setting"]
        >= gates["minimum_idempotent_state_setting_opportunities"],
        "read_only_gate": opportunities["read_only"]
        >= gates["minimum_read_only_opportunities"],
    }
    boundary = config["boundary"]
    boundary_checks = {
        key: boundary.get(key) is False
        for key in (
            "model_loaded",
            "model_outputs_read",
            "bundled_historical_results_read",
            "target_tasks_executed",
            "gpu_used",
            "method_receives_audit_metadata",
            "development_model_run_authorized",
            "confirmatory_claim_authorized",
        )
    }
    checks = {
        "static_input_only_mode": config.get("mode")
        == "cpu_static_inputs_only_no_model_no_trajectory_no_task_execution",
        "repository_revision_matches": _git(source, "rev-parse", "HEAD")
        == config["repository"]["revision"],
        "repository_tag_object_matches": _git(
            source, "rev-parse", config["repository"]["tag"]
        )
        == config["repository"]["tag_object"],
        "repository_tag_matches": _git(source, "describe", "--tags", "--exact-match")
        == config["repository"]["tag"],
        "repository_checkout_clean": _git(source, "status", "--porcelain") == "",
        "selected_input_hashes_match": source_hashes_match,
        "no_forbidden_source_path_selected": not forbidden_selected,
        "domain_counts_and_splits_match": domain_counts_match,
        "public_tool_contracts_resolve": all_contracts_resolve,
        "assistant_action_contract_coverage": no_uncovered_actions,
        "source_capacity_gates_pass": all(capacity_checks.values()),
        "no_model_or_execution_authority": all(boundary_checks.values()),
        "native_recoverable_pairs_not_claimed": config["next_gate"][
            "native_recoverable_pairs_claimed"
        ]
        == 0,
        "target_capacity_not_prematurely_claimed": config["next_gate"][
            "target_capacity_claimed"
        ]
        == 0,
    }
    passed = all(checks.values())
    partition_records.sort(key=lambda item: (item["domain"], item["task_id"]))
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_3_tau3_source_qualification",
        "passed": passed,
        "checks": checks,
        "repository": {
            "name": config["repository"]["name"],
            "url": config["repository"]["url"],
            "tag": config["repository"]["tag"],
            "revision": config["repository"]["revision"],
            "selected_input_manifest_sha256": _canonical_sha256(source_manifest),
            "selected_input_count": len(source_manifest),
        },
        "domain_summaries": domain_summaries,
        "static_continuation_opportunities": {
            effect: opportunities[effect] for effect in EFFECT_CLASSES
        },
        "static_continuation_opportunity_count": total_count,
        "capacity_checks": capacity_checks,
        "prospective_partition": {
            "development_task_count": sum(
                record["partition"] == "development" for record in partition_records
            ),
            "heldout_task_count": sum(
                record["partition"] == "heldout" for record in partition_records
            ),
            "preservation_task_count": sum(
                record["partition"] == "preservation"
                for record in partition_records
            ),
            "manifest_sha256": _canonical_sha256(partition_records),
            "labels_are_prospective_not_qualified_targets": True,
        },
        "source_qualified_for_cpu_branch_screening": passed,
        "new_target_capacity_available": False,
        "native_recoverable_pair_count": 0,
        "development_model_run_authorized": False,
        "confirmatory_run_authorized": False,
        "next_gate": "cpu_scripted_recoverable_branch_validation",
        "pending_exclusion_audits": config["next_gate"][
            "required_exclusion_audits"
        ],
        "disposition": (
            "continue_cpu_branch_screening" if passed else "stop_source_qualification"
        ),
        "boundary": {
            "model_loaded": False,
            "model_outputs_read": False,
            "bundled_historical_results_read": False,
            "target_tasks_executed": False,
            "gpu_used": False,
            "evaluator_actions_used_only_as_audit_depth_proxies": True,
            "audit_metadata_passed_to_method": False,
        },
        "interpretation": (
            "The pinned source has sufficient static multi-step and action-effect "
            "diversity for a CPU scripted recoverable-branch screen. It does not "
            "yet contribute a qualified development, held-out, or confirmatory pair."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = qualify_source(args.config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(
        (
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
    )
    print(
        json.dumps(
            {
                "passed": result["passed"],
                "disposition": result["disposition"],
                "static_continuation_opportunity_count": result[
                    "static_continuation_opportunity_count"
                ],
                "new_target_capacity_available": result[
                    "new_target_capacity_available"
                ],
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
