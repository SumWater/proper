from __future__ import annotations

import argparse
import copy
import importlib.metadata
import json
import os
import platform
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

import yaml


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "external" / "toolmisusebench"))

from agent_runtime import (  # noqa: E402
    TransformersQwenClient,
    action_payload,
    build_prompt,
    canonical,
    prepare_prefix,
    sha256_file,
    sha256_text,
    verify_source_manifest,
)
from benchmark_instances import (  # noqa: E402
    RETRY_POLICY,
    experience_text,
    make_actual_instance,
)
from confirmatory_gate_v1 import (  # noqa: E402
    frozen_memory_bank,
    verify_test_file,
)
from gate_dataset import (  # noqa: E402
    condition_result,
    ensure_agent_boundary,
    load_config as load_memory_config,
    resolve_root_path,
    verify_model_files,
)
from failure_memory.confirmatory import (  # noqa: E402
    aggregate_pair_indicators,
    behavior_atoms,
    indicators_payload,
    pair_indicators,
)
from toolmisusebench.dataset import load_tasks  # noqa: E402


CONFIG = ROOT / "configs" / "proper_v1" / "confirmatory_transient_authz_v1.yaml"
FORMAL_LOCK = ROOT / "configs" / "proper_v1" / "confirmatory_transient_authz_v1.lock.json"
PREPARED_LOCK = (
    ROOT / "configs" / "proper_v1" / "confirmatory_transient_authz_v1.prepared.lock.json"
)
ENVIRONMENT_LOCK = (
    ROOT / "configs" / "proper_v1" / "confirmatory_transient_authz_v1.environment.lock.json"
)
CAPACITY_RESULT_LOCK = ROOT / "configs" / "proper_v1" / "transient_authz_capacity_v1.result.lock.json"
FORMAL_RUNTIME_CONFIG = ROOT / "configs" / "proper_v1" / "confirmatory_gate_v1.runtime.yaml"
TOOLMISUSEBENCH_LOCK = ROOT / "configs" / "proper_v1" / "toolmisusebench.lock.json"


def verify_formal_lock() -> dict[str, Any]:
    lock = json.loads(FORMAL_LOCK.read_text(encoding="utf-8"))
    if (
        lock.get("status")
        != "frozen_after_preparation_before_native_authz_model_outputs"
    ):
        raise RuntimeError("formal transient-authz source lock has invalid status")
    for key in (
        "config",
        "runner",
        "selector",
        "result_schema",
        "preregistration",
        "capacity_result_lock",
        "capacity_screening",
        "environment_lock",
        "preparation_lock",
        "preparation_report",
        "run_script",
    ):
        item = lock[key]
        if sha256_file(resolve_root_path(item["path"])) != str(item["sha256"]):
            raise RuntimeError(f"formal transient-authz source mismatch: {key}")
    if lock["model_outputs_generated"] or not lock["gpu_run_authorized"]:
        raise RuntimeError("formal lock does not authorize the frozen GPU run")
    return lock


def verify_environment_lock(config: Mapping[str, Any]) -> dict[str, Any]:
    lock = json.loads(ENVIRONMENT_LOCK.read_text(encoding="utf-8"))
    if lock.get("status") != "frozen_before_native_authz_model_outputs":
        raise RuntimeError("transient-authz environment lock has invalid status")
    for key in ("conda_explicit_lock", "pip_freeze_lock"):
        item = lock[key]
        if sha256_file(resolve_root_path(item["path"])) != str(item["sha256"]):
            raise RuntimeError(f"transient-authz environment artifact mismatch: {key}")
    if lock["conda_explicit_lock"]["sha256"] != str(
        config["environment"]["conda_explicit_sha256"]
    ):
        raise RuntimeError("config and conda environment lock disagree")
    if lock["pip_freeze_lock"]["sha256"] != str(
        config["environment"]["pip_freeze_sha256"]
    ):
        raise RuntimeError("config and pip environment lock disagree")
    for distribution, expected in lock["required_distribution_versions"].items():
        actual = importlib.metadata.version(distribution)
        if actual != expected:
            raise RuntimeError(
                f"runtime distribution mismatch: {distribution} "
                f"expected={expected}, observed={actual}"
            )
    return lock


def verify_prepared_lock(config: Mapping[str, Any]) -> dict[str, Any]:
    lock = json.loads(PREPARED_LOCK.read_text(encoding="utf-8"))
    if lock.get("status") != "pass_deterministic_preparation_before_model_outputs":
        raise RuntimeError("prepared transient-authz lock has invalid status")
    for key in (
        "prepared_manifest",
        "screening",
        "conda_explicit_lock",
        "pip_freeze_lock",
    ):
        item = lock[key]
        if sha256_file(resolve_root_path(item["path"])) != str(item["sha256"]):
            raise RuntimeError(f"prepared transient-authz artifact mismatch: {key}")
    prepared = json.loads(
        resolve_root_path(lock["prepared_manifest"]["path"]).read_text(encoding="utf-8")
    )
    if prepared["identities"]["prepared_payload_sha256"] != str(
        lock["prepared_payload_sha256"]
    ):
        raise RuntimeError("prepared payload identity differs from authorization lock")
    screening = prepared["screening"]
    expected = {
        "all_target_count": lock["all_target_count"],
        "primary_selection_changed_pair_count": lock["primary_pair_count"],
        "planned_model_call_count": lock["planned_model_call_count"],
        "global_distinct_prompt_count": lock["global_distinct_prompt_count"],
    }
    for key, value in expected.items():
        if screening[key] != value:
            raise RuntimeError(f"prepared authorization count mismatch: {key}")
    if not lock["gpu_run_authorized"] or lock["model_outputs_read_or_generated"]:
        raise RuntimeError("prepared artifact does not authorize model execution")
    if resolve_root_path(config["outputs"]["prepared_manifest"]) != resolve_root_path(
        lock["prepared_manifest"]["path"]
    ):
        raise RuntimeError("config and prepared authorization lock disagree")
    return lock


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if config.get("status") != "frozen_before_native_authz_model_outputs":
        raise RuntimeError("confirmatory transient-authz config has invalid status")
    if not bool(config["cohort"]["persistent_authorization_excluded"]):
        raise RuntimeError("persistent authorization must remain excluded")
    return config


def load_capacity(config: Mapping[str, Any]) -> dict[str, Any]:
    frozen = config["frozen_capacity"]
    capacity_config = resolve_root_path(frozen["config"])
    capacity_screening = resolve_root_path(frozen["screening"])
    if sha256_file(capacity_config) != str(frozen["config_sha256"]):
        raise RuntimeError("frozen capacity config hash mismatch")
    if sha256_file(capacity_screening) != str(frozen["screening_sha256"]):
        raise RuntimeError("frozen capacity screening hash mismatch")
    result_lock = json.loads(CAPACITY_RESULT_LOCK.read_text(encoding="utf-8"))
    if result_lock["decision"] != "PASS_TRANSIENT_AUTHZ_PUBLIC_TEST_CAPACITY":
        raise RuntimeError("capacity result did not authorize protocol preparation")
    if result_lock["screening"]["sha256"] != str(frozen["screening_sha256"]):
        raise RuntimeError("capacity result lock disagrees with formal config")
    payload = json.loads(capacity_screening.read_text(encoding="utf-8"))
    if payload["boundary"]["model_outputs_read"]:
        raise RuntimeError("capacity screening unexpectedly read model outputs")
    if len(payload["records"]) != int(frozen["expected_all_target_count"]):
        raise RuntimeError("frozen all-target count mismatch")
    primary = sum(bool(item["selection_changed"]) for item in payload["records"])
    if primary != int(frozen["expected_primary_pair_count"]):
        raise RuntimeError("frozen primary-pair count mismatch")
    return payload


def load_instances_and_memories(
    config: Mapping[str, Any], capacity: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    formal_config = yaml.safe_load(FORMAL_RUNTIME_CONFIG.read_text(encoding="utf-8"))
    public_test = verify_test_file(formal_config)
    if sha256_file(public_test) != str(config["dataset"]["sha256"]):
        raise RuntimeError("formal config and runtime disagree on public-test hash")
    tasks = load_tasks(public_test.parent, str(config["dataset"]["split"]))
    if len(tasks) != int(config["dataset"]["expected_task_count"]):
        raise RuntimeError("unexpected public-test task count")
    task_by_id = {task.task_id: task for task in tasks}

    sources, frozen_memory = frozen_memory_bank(formal_config)
    if len(sources) != int(config["memory_bank"]["source_count"]):
        raise RuntimeError("unexpected frozen memory source count")
    if sha256_file(resolve_root_path(config["memory_bank"]["prepared_manifest"])) != str(
        config["memory_bank"]["prepared_manifest_sha256"]
    ):
        raise RuntimeError("formal memory manifest hash mismatch")
    if frozen_memory["identities"]["prepared_payload_sha256"] != str(
        config["memory_bank"]["prepared_payload_sha256"]
    ):
        raise RuntimeError("formal memory payload hash mismatch")
    memories = {
        f"experience::{source.instance_id}": source for source in sources
    }
    source_task_ids = {source.source_task_id for source in sources}

    instances: dict[str, Any] = {}
    for record in capacity["records"]:
        source_task_id = str(record["source_task_id"])
        if source_task_id in source_task_ids:
            raise RuntimeError("dev memory source overlaps public-test target")
        task = task_by_id.get(source_task_id)
        if task is None:
            raise RuntimeError(f"capacity target is absent from public test: {source_task_id}")
        instance = make_actual_instance(task, "authorization_transient", RETRY_POLICY)
        if instance is None or not instance.released_condition:
            raise RuntimeError(f"capacity target no longer reconstructs: {source_task_id}")
        if instance.instance_id != record["instance_id"]:
            raise RuntimeError("capacity instance identity mismatch")
        instances[instance.instance_id] = instance
    if len(instances) != len(capacity["records"]):
        raise RuntimeError("duplicate formal target instances")
    return instances, memories, frozen_memory


def prepare_payload(
    config_path: Path = CONFIG,
) -> tuple[dict[str, Any], dict[str, Any]]:
    config = load_config(config_path)
    capacity = load_capacity(config)
    instances, memories, frozen_memory = load_instances_and_memories(config, capacity)
    boundary_config = load_memory_config()

    records = []
    all_prompt_hashes: set[str] = set()
    planned_model_call_count = 0
    for frozen_record in capacity["records"]:
        instance = instances[frozen_record["instance_id"]]
        _, visible, prefix_sha256 = prepare_prefix(instance)
        if prefix_sha256 != frozen_record["prefix_sha256"]:
            raise RuntimeError("formal failure prefix differs from capacity screening")
        rank1 = memories.get(frozen_record["rank1_experience_id"])
        selected = memories.get(frozen_record["selected_experience_id"])
        if rank1 is None or selected is None:
            raise RuntimeError("formal selected memory is absent from frozen bank")
        prompts = {
            "tfidf_rank1_memory": build_prompt(visible, experience_text(rank1)),
            "proper_transient_authz_memory": build_prompt(visible, experience_text(selected)),
        }
        ensure_agent_boundary(prompts.values(), boundary_config)
        prompt_sha256 = {name: sha256_text(prompt) for name, prompt in prompts.items()}
        all_prompt_hashes.update(prompt_sha256.values())
        planned_model_call_count += len(set(prompt_sha256.values()))
        records.append(
            {
                "instance_id": instance.instance_id,
                "source_task_id": instance.source_task_id,
                "seed": instance.task.seed,
                "target_tool_name": frozen_record["target_tool_name"],
                "prefix_sha256": prefix_sha256,
                "failed_action": action_payload(instance.failure_action),
                "rank1_experience_id": frozen_record["rank1_experience_id"],
                "rank1_policy": frozen_record["rank1_policy"],
                "proper_experience_id": frozen_record["selected_experience_id"],
                "proper_selected_original_rank": frozen_record[
                    "selected_original_rank"
                ],
                "proper_selected_same_tool_memory": frozen_record[
                    "selected_same_tool_memory"
                ],
                "selection_changed": frozen_record["selection_changed"],
                "prompts": prompts,
                "prompt_sha256": prompt_sha256,
            }
        )

    expected_calls = int(config["frozen_capacity"]["expected_model_call_count"])
    if planned_model_call_count != expected_calls:
        raise RuntimeError(
            "unexpected planned model call count: "
            f"expected={expected_calls}, observed={planned_model_call_count}"
        )
    expected_distinct = int(
        config["frozen_capacity"]["expected_global_distinct_prompt_count"]
    )
    if len(all_prompt_hashes) != expected_distinct:
        raise RuntimeError(
            "unexpected global distinct prompt count: "
            f"expected={expected_distinct}, observed={len(all_prompt_hashes)}"
        )
    primary_count = sum(item["selection_changed"] for item in records)
    screening = {
        "all_target_count": len(records),
        "primary_selection_changed_pair_count": primary_count,
        "unchanged_target_count": len(records) - primary_count,
        "planned_model_call_count": planned_model_call_count,
        "global_distinct_prompt_count": len(all_prompt_hashes),
        "distinct_primary_target_tool_count": len(
            {item["target_tool_name"] for item in records if item["selection_changed"]}
        ),
        "distinct_primary_selected_memory_count": len(
            {item["proper_experience_id"] for item in records if item["selection_changed"]}
        ),
        "gpu_run_authorized_by_capacity": (
            primary_count == int(config["frozen_capacity"]["expected_primary_pair_count"])
        ),
    }
    payload = {
        "schema_version": 1,
        "run_kind": "confirmatory_transient_authz_v1_prepared",
        "identities": {
            "config_sha256": sha256_file(config_path),
            "capacity_screening_sha256": sha256_file(
                resolve_root_path(config["frozen_capacity"]["screening"])
            ),
            "capacity_result_lock_sha256": sha256_file(CAPACITY_RESULT_LOCK),
            "public_test_sha256": config["dataset"]["sha256"],
            "frozen_memory_bank_manifest_sha256": config["memory_bank"][
                "prepared_manifest_sha256"
            ],
            "frozen_memory_bank_payload_sha256": frozen_memory["identities"][
                "prepared_payload_sha256"
            ],
        },
        "boundary": {
            "released_transient_authorization_only": True,
            "persistent_authorization_excluded": True,
            "model_loaded": False,
            "model_outputs_read": False,
            "selector_hidden_labels_used": False,
            "memory_source_split": "dev",
            "target_split": "test_public",
        },
        "screening": screening,
        "records": records,
    }
    payload["identities"]["prepared_payload_sha256"] = sha256_text(canonical(payload))
    return payload, instances


def write_prepared(payload: Mapping[str, Any], config: Mapping[str, Any]) -> None:
    prepared = resolve_root_path(config["outputs"]["prepared_manifest"])
    screening = resolve_root_path(config["outputs"]["screening_output"])
    prepared.parent.mkdir(parents=True, exist_ok=True)
    screening.parent.mkdir(parents=True, exist_ok=True)
    prepared.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    screening_payload = {key: value for key, value in payload.items() if key != "records"}
    screening_payload["run_kind"] = "confirmatory_transient_authz_v1_screening"
    screening.write_text(
        json.dumps(screening_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def aggregate_pairs(
    indicators: list[Any], baseline: list[bool], proper: list[bool], alpha: float
) -> dict[str, Any]:
    result = aggregate_pair_indicators(indicators, baseline, proper, alpha=alpha)
    result["directional_hypothesis_supported"] = (
        result["paired_positive_transfer_count"]
        > result["paired_negative_transfer_count"]
        and result["exact_mcnemar_two_sided_p"] < alpha
    )
    result["hypothesis_direction"] = "ppt_greater_than_pnt"
    return result


def secondary_summary(condition_rows: Mapping[str, list[dict[str, Any]]]) -> dict[str, Any]:
    summary = {}
    for condition, rows in condition_rows.items():
        summary[condition] = {
            "recovery_validity_count": sum(item["outcome"]["recovery_validity"] for item in rows),
            "task_completion_count": sum(item["outcome"]["task_completion"] for item in rows),
            "safety_violation_count": sum(item["outcome"]["safety_violation"] for item in rows),
            "repeated_invalid_calls_total": sum(
                item["outcome"]["repeated_invalid_calls"] for item in rows
            ),
            "exact_retry_count": sum(item["behavior_atoms"]["exact_retry"] for item in rows),
        }
    return summary


def run_formal(args: argparse.Namespace, config: dict[str, Any]) -> int:
    prepared_path = resolve_root_path(config["outputs"]["prepared_manifest"])
    frozen = json.loads(prepared_path.read_text(encoding="utf-8"))
    rebuilt, instances = prepare_payload(args.config)
    if canonical(frozen) != canonical(rebuilt):
        raise RuntimeError("prepared transient-authz cohort does not reconstruct exactly")
    if not frozen["screening"]["gpu_run_authorized_by_capacity"]:
        raise RuntimeError("frozen capacity does not authorize model execution")

    project_manifest_sha256 = verify_source_manifest(args.project_manifest)
    verify_model_files(args.model.resolve(), args.model_manifest)
    if sha256_file(args.model_manifest) != str(config["model"]["manifest_sha256"]):
        raise RuntimeError("model manifest mismatch")
    if sha256_file(args.conda_lock) != str(config["environment"]["conda_explicit_sha256"]):
        raise RuntimeError("conda environment lock mismatch")
    if sha256_file(args.pip_lock) != str(config["environment"]["pip_freeze_sha256"]):
        raise RuntimeError("pip environment lock mismatch")

    client = TransformersQwenClient(
        model_path=args.model.resolve(),
        load_in_4bit=args.load_in_4bit,
        max_new_tokens=int(config["model"]["max_new_tokens"]),
    )
    fixed_order = config["conditions"]["fixed_order"]
    output_records = []
    all_indicators = []
    all_baseline: list[bool] = []
    all_proper: list[bool] = []
    primary_indicators = []
    primary_baseline: list[bool] = []
    primary_proper: list[bool] = []
    condition_rows: dict[str, list[dict[str, Any]]] = {name: [] for name in fixed_order}
    model_call_count = 0
    parse_failures = 0
    tool_rows: dict[str, list[tuple[Any, bool, bool]]] = defaultdict(list)

    for record in frozen["records"]:
        instance = instances[record["instance_id"]]
        conditions: dict[str, Any] = {}
        decisions: dict[str, Any] = {}
        outcomes: dict[str, Any] = {}
        completed: dict[str, tuple[Any, Any, dict[str, Any], str]] = {}
        for condition in fixed_order:
            prompt = record["prompts"][condition]
            prompt_hash = record["prompt_sha256"][condition]
            if prompt_hash in completed:
                decision, outcome, original_result, original_condition = completed[prompt_hash]
                result = copy.deepcopy(original_result)
                result["reused_from_condition"] = original_condition
            else:
                (decision, outcome), result = condition_result(
                    client=client,
                    instance=instance,
                    prompt=prompt,
                    seed=int(record["seed"]),
                )
                result["reused_from_condition"] = None
                completed[prompt_hash] = (decision, outcome, copy.deepcopy(result), condition)
                model_call_count += 1
                parse_failures += int(not result["parse_valid"])
            if result["prompt_sha256"] != prompt_hash:
                raise RuntimeError("formal prompt identity mismatch")
            if result["prefix_hash"] != record["prefix_sha256"]:
                raise RuntimeError("paired failure prefix mismatch")
            decisions[condition] = decision
            outcomes[condition] = outcome
            conditions[condition] = result

        baseline_name, proper_name = fixed_order
        for condition in fixed_order:
            conditions[condition]["behavior_atoms"] = behavior_atoms(
                failed_action=record["failed_action"],
                no_memory_decision=decisions[baseline_name],
                condition_decision=decisions[condition],
                schema_verification_tools=(),
            )
            condition_rows[condition].append(conditions[condition])

        indicator = pair_indicators(
            no_memory_recovery_validity=outcomes[baseline_name].recovery_validity,
            memory_recovery_validity=outcomes[proper_name].recovery_validity,
            no_memory_decision=decisions[baseline_name],
            memory_decision=decisions[proper_name],
            strict_policy_adoption=conditions[proper_name]["behavior_atoms"]["exact_retry"],
        )
        all_indicators.append(indicator)
        all_baseline.append(outcomes[baseline_name].recovery_validity)
        all_proper.append(outcomes[proper_name].recovery_validity)
        if record["selection_changed"]:
            primary_indicators.append(indicator)
            primary_baseline.append(outcomes[baseline_name].recovery_validity)
            primary_proper.append(outcomes[proper_name].recovery_validity)
            tool_rows[record["target_tool_name"]].append(
                (
                    indicator,
                    outcomes[baseline_name].recovery_validity,
                    outcomes[proper_name].recovery_validity,
                )
            )
        output_records.append(
            {
                **{key: value for key, value in record.items() if key != "prompts"},
                "conditions": conditions,
                "proper_vs_rank1_indicators": indicators_payload(indicator),
            }
        )

    expected_calls = int(config["frozen_capacity"]["expected_model_call_count"])
    if model_call_count != expected_calls:
        raise RuntimeError("model call count differs from preregistration")
    alpha = float(config["primary_endpoint"]["alpha"])
    primary = aggregate_pairs(primary_indicators, primary_baseline, primary_proper, alpha)
    all_targets = aggregate_pairs(all_indicators, all_baseline, all_proper, alpha)
    all_targets["confirmatory_test_performed"] = False
    tool_strata = {}
    for tool, rows in sorted(tool_rows.items()):
        indicators = [item[0] for item in rows]
        baseline = [item[1] for item in rows]
        proper = [item[2] for item in rows]
        value = aggregate_pairs(indicators, baseline, proper, alpha)
        value["confirmatory_test_performed"] = False
        tool_strata[tool] = value

    report = {
        "schema_version": 1,
        "run_kind": "confirmatory_transient_authz_v1_results",
        "identities": {
            **frozen["identities"],
            "prepared_file_sha256": sha256_file(prepared_path),
            "project_source_manifest_sha256": project_manifest_sha256,
            "model_manifest_sha256": sha256_file(args.model_manifest),
            "conda_explicit_lock_sha256": sha256_file(args.conda_lock),
            "pip_freeze_lock_sha256": sha256_file(args.pip_lock),
            "toolmisusebench_lock_sha256": sha256_file(TOOLMISUSEBENCH_LOCK),
            "python": sys.version,
            "platform": platform.platform(),
        },
        "screening": frozen["screening"],
        "primary_comparison": primary,
        "descriptive_all_targets": all_targets,
        "secondary_outcomes": {
            "conditions": secondary_summary(condition_rows),
            "primary_tool_strata": tool_strata,
            "primary_selected_memory_counts": dict(
                sorted(
                    Counter(
                        item["proper_experience_id"]
                        for item in frozen["records"]
                        if item["selection_changed"]
                    ).items()
                )
            ),
        },
        "model_output_parse_failure_count": parse_failures,
        "model_call_count": model_call_count,
        "records": output_records,
    }
    output = resolve_root_path(config["outputs"]["result_output"])
    if output.exists():
        raise RuntimeError("refusing to overwrite a formal transient-authz result")
    for protected in config["outputs"]["never_overwrite"]:
        if output.resolve() == resolve_root_path(protected).resolve():
            raise RuntimeError("formal output would overwrite prior evidence")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({key: value for key, value in report.items() if key != "records"}, indent=2))
    print("RESULT=COMPLETE_CONFIRMATORY_TRANSIENT_AUTHZ_V1")
    return 0


def cpu_dry_run(config: Mapping[str, Any]) -> dict[str, Any]:
    capacity = load_capacity(config)
    first = next(item for item in capacity["records"] if item["selection_changed"])
    visible = {
        "instruction": "Use the requested tool.",
        "last_error": {"code": "authz_denied", "message": "Denied", "details": {}},
        "tool_schemas": [],
        "transcript": [],
        "remaining_budget": {"steps_left": 1, "tool_calls_left": 1, "retries_left": 1},
    }
    prompts = {
        "tfidf_rank1_memory": build_prompt(visible, "A prior agent stopped."),
        "proper_transient_authz_memory": build_prompt(visible, "A prior agent retried once."),
    }
    return {
        "model_loaded": False,
        "public_test_read": False,
        "synthetic_non_model_output": True,
        "capacity_target_count": len(capacity["records"]),
        "primary_pair_count": sum(item["selection_changed"] for item in capacity["records"]),
        "example_instance_id_sha256": sha256_text(str(first["instance_id"])),
        "condition_count": len(prompts),
        "distinct_prompt_count": len({sha256_text(value) for value in prompts.values()}),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Confirmatory transient authorization v1")
    parser.add_argument("--config", type=Path, default=CONFIG)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--cpu-dry-run", action="store_true")
    mode.add_argument("--run", action="store_true")
    parser.add_argument("--model", type=Path)
    parser.add_argument("--load-in-4bit", action="store_true")
    parser.add_argument("--conda-lock", type=Path)
    parser.add_argument("--pip-lock", type=Path)
    parser.add_argument("--model-manifest", type=Path)
    parser.add_argument("--project-manifest", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    verify_formal_lock()
    config = load_config(args.config)
    if args.cpu_dry_run:
        print(json.dumps(cpu_dry_run(config), indent=2, sort_keys=True))
        print("RESULT=PASS_CONFIRMATORY_TRANSIENT_AUTHZ_V1_CPU_DRY_RUN")
        return 0
    if args.prepare:
        payload, _ = prepare_payload(args.config)
        write_prepared(payload, config)
        print(json.dumps(payload["screening"], indent=2, sort_keys=True))
        print("RESULT=PASS_CONFIRMATORY_TRANSIENT_AUTHZ_V1_PREPARATION")
        print("NOTE=No model was loaded and no model output was generated.")
        return 0
    required = ("model", "conda_lock", "pip_lock", "model_manifest", "project_manifest")
    missing = [name for name in required if getattr(args, name) is None]
    if missing:
        raise RuntimeError(f"missing formal inputs: {missing}")
    verify_prepared_lock(config)
    verify_environment_lock(config)
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    return run_formal(args, config)


if __name__ == "__main__":
    raise SystemExit(main())
