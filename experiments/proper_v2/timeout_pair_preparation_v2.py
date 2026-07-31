from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

import yaml


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "external" / "toolmisusebench"))
sys.path.insert(0, str(ROOT / "experiments" / "proper_v1"))

from agent_runtime import (  # noqa: E402
    action_payload,
    build_prompt,
    canonical,
    prepare_prefix,
    sha256_file,
    sha256_text,
)
from benchmark_instances import (  # noqa: E402
    RETRY_POLICY,
    experience_text,
    make_actual_instance,
)
from confirmatory_gate_v1 import frozen_memory_bank, verify_test_file  # noqa: E402
from gate_dataset import (  # noqa: E402
    ensure_agent_boundary,
    load_config as load_memory_config,
    resolve_root_path,
)
from toolmisusebench.dataset import load_tasks  # noqa: E402


CONFIG = ROOT / "configs" / "proper_v2" / "timeout_pair_v2.yaml"
FORMAL_RUNTIME_CONFIG = (
    ROOT / "configs" / "proper_v1" / "confirmatory_gate_v1.runtime.yaml"
)


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if config.get("status") != "preparation_protocol_before_timeout_model_outputs":
        raise RuntimeError("timeout paired preparation config has invalid status")
    if bool(config["boundary"]["gpu_run_authorized_at_preparation_stage"]):
        raise RuntimeError("preparation-stage config cannot authorize GPU execution")
    return config


def load_capacity(config: Mapping[str, Any]) -> dict[str, Any]:
    frozen = config["frozen_capacity"]
    capacity_config = resolve_root_path(frozen["config"])
    capacity_screening = resolve_root_path(frozen["screening"])
    if sha256_file(capacity_config) != str(frozen["config_sha256"]):
        raise RuntimeError("frozen timeout capacity config hash mismatch")
    if sha256_file(capacity_screening) != str(frozen["screening_sha256"]):
        raise RuntimeError("frozen timeout capacity screening hash mismatch")
    payload = json.loads(capacity_screening.read_text(encoding="utf-8"))
    boundary = payload["boundary"]
    if boundary["model_loaded"] or boundary["model_outputs_read"]:
        raise RuntimeError("capacity artifact unexpectedly contains model activity")
    if not payload["screening"]["future_protocol_preparation_authorized"]:
        raise RuntimeError("capacity artifact did not authorize protocol preparation")
    if len(payload["records"]) != int(frozen["expected_all_target_count"]):
        raise RuntimeError("frozen all-target count mismatch")
    changed = sum(bool(item["selection_changed"]) for item in payload["records"])
    if changed != int(frozen["expected_primary_pair_count"]):
        raise RuntimeError("frozen primary-pair count mismatch")
    return payload


def load_instances_and_memories(
    config: Mapping[str, Any], capacity: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    runtime = yaml.safe_load(FORMAL_RUNTIME_CONFIG.read_text(encoding="utf-8"))
    public_test = verify_test_file(runtime)
    if sha256_file(public_test) != str(config["dataset"]["sha256"]):
        raise RuntimeError("formal config and runtime disagree on public-test hash")
    tasks = load_tasks(public_test.parent, str(config["dataset"]["split"]))
    if len(tasks) != int(config["dataset"]["expected_task_count"]):
        raise RuntimeError("unexpected public-test task count")
    task_by_id = {task.task_id: task for task in tasks}

    sources, frozen_memory = frozen_memory_bank(runtime)
    manifest = resolve_root_path(config["memory_bank"]["prepared_manifest"])
    if sha256_file(manifest) != str(
        config["memory_bank"]["prepared_manifest_sha256"]
    ):
        raise RuntimeError("formal memory manifest hash mismatch")
    if frozen_memory["identities"]["prepared_payload_sha256"] != str(
        config["memory_bank"]["prepared_payload_sha256"]
    ):
        raise RuntimeError("formal memory payload hash mismatch")
    if len(sources) != int(config["memory_bank"]["source_count"]):
        raise RuntimeError("unexpected frozen memory source count")
    memories = {f"experience::{source.instance_id}": source for source in sources}
    source_task_ids = {source.source_task_id for source in sources}

    instances: dict[str, Any] = {}
    for record in capacity["records"]:
        source_task_id = str(record["source_task_id"])
        if source_task_id in source_task_ids:
            raise RuntimeError("dev memory source overlaps public-test target")
        task = task_by_id.get(source_task_id)
        if task is None:
            raise RuntimeError(f"capacity target absent from public test: {source_task_id}")
        instance = make_actual_instance(task, "timeout_transient", RETRY_POLICY)
        if instance is None or not instance.released_condition:
            raise RuntimeError(f"timeout target no longer reconstructs: {source_task_id}")
        if instance.instance_id != record["instance_id"]:
            raise RuntimeError("capacity instance identity mismatch")
        instances[instance.instance_id] = instance
    if len(instances) != len(capacity["records"]):
        raise RuntimeError("duplicate timeout target instances")
    return instances, memories, frozen_memory


def prepare_payload(
    config_path: Path = CONFIG,
) -> tuple[dict[str, Any], dict[str, Any]]:
    config = load_config(config_path)
    capacity = load_capacity(config)
    instances, memories, frozen_memory = load_instances_and_memories(config, capacity)
    boundary_config = load_memory_config()

    records = []
    global_prompt_hashes: set[str] = set()
    planned_model_call_count = 0
    for frozen_record in capacity["records"]:
        instance = instances[frozen_record["instance_id"]]
        _, visible, prefix_sha256 = prepare_prefix(instance)
        if prefix_sha256 != frozen_record["prefix_sha256"]:
            raise RuntimeError("failure prefix differs from capacity screening")
        rank1 = memories.get(frozen_record["rank1_experience_id"])
        selected = memories.get(frozen_record["selected_experience_id"])
        if rank1 is None or selected is None:
            raise RuntimeError("selected memory absent from frozen bank")
        prompts = {
            "tfidf_rank1_memory": build_prompt(visible, experience_text(rank1)),
            "proper_v2_memory": build_prompt(visible, experience_text(selected)),
        }
        ensure_agent_boundary(prompts.values(), boundary_config)
        prompt_sha256 = {
            name: sha256_text(prompt) for name, prompt in prompts.items()
        }
        global_prompt_hashes.update(prompt_sha256.values())
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
                "rank1_operation": frozen_record["rank1_operation"],
                "proper_experience_id": frozen_record["selected_experience_id"],
                "proper_selected_original_rank": frozen_record[
                    "selected_original_rank"
                ],
                "proper_operation": frozen_record["selected_operation"],
                "selection_changed": frozen_record["selection_changed"],
                "selector_abstained": frozen_record["abstained"],
                "prompts": prompts,
                "prompt_sha256": prompt_sha256,
            }
        )

    expected_calls = int(
        config["frozen_capacity"]["expected_planned_model_call_count"]
    )
    if planned_model_call_count != expected_calls:
        raise RuntimeError(
            "unexpected planned model call count: "
            f"expected={expected_calls}, observed={planned_model_call_count}"
        )
    primary_count = sum(item["selection_changed"] for item in records)
    screening = {
        "all_target_count": len(records),
        "primary_selection_changed_pair_count": primary_count,
        "unchanged_target_count": len(records) - primary_count,
        "planned_model_call_count": planned_model_call_count,
        "global_distinct_prompt_count": len(global_prompt_hashes),
        "distinct_primary_target_tool_count": len(
            {
                item["target_tool_name"]
                for item in records
                if item["selection_changed"]
            }
        ),
        "distinct_primary_selected_memory_count": len(
            {
                item["proper_experience_id"]
                for item in records
                if item["selection_changed"]
            }
        ),
        "gpu_run_authorized": False,
        "ready_for_source_and_environment_lock": (
            primary_count
            == int(config["frozen_capacity"]["expected_primary_pair_count"])
            and planned_model_call_count == expected_calls
        ),
    }
    payload = {
        "schema_version": 1,
        "run_kind": "proper_v2_timeout_pair_prepared",
        "identities": {
            "config_sha256": sha256_file(config_path),
            "capacity_screening_sha256": sha256_file(
                resolve_root_path(config["frozen_capacity"]["screening"])
            ),
            "public_test_sha256": config["dataset"]["sha256"],
            "frozen_memory_bank_manifest_sha256": config["memory_bank"][
                "prepared_manifest_sha256"
            ],
            "frozen_memory_bank_payload_sha256": frozen_memory["identities"][
                "prepared_payload_sha256"
            ],
        },
        "boundary": {
            "released_native_timeout_only": True,
            "prior_used_base_tasks_excluded": True,
            "model_loaded": False,
            "model_outputs_read": False,
            "selector_hidden_labels_used": False,
            "memory_source_split": "dev",
            "target_split": "test_public",
            "gpu_run_authorized": False,
        },
        "screening": screening,
        "records": records,
    }
    payload["identities"]["prepared_payload_sha256"] = sha256_text(
        canonical(payload)
    )
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
    screening_payload["run_kind"] = "proper_v2_timeout_pair_screening"
    screening.write_text(
        json.dumps(screening_payload, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def cpu_dry_run(config: Mapping[str, Any]) -> dict[str, Any]:
    capacity = load_capacity(config)
    changed = [item for item in capacity["records"] if item["selection_changed"]]
    visible = {
        "instruction": "Read the requested file.",
        "last_error": {
            "code": "timeout",
            "message": "Tool call timed out.",
            "details": {"timeout_ms": 50},
        },
        "tool_schemas": [],
        "transcript": [],
        "remaining_budget": {
            "steps_left": 1,
            "tool_calls_left": 1,
            "retries_left": 1,
        },
    }
    prompts = {
        "tfidf_rank1_memory": build_prompt(visible, "A previous recovery repaired arguments."),
        "proper_v2_memory": build_prompt(visible, "A previous recovery retried once."),
    }
    return {
        "model_loaded": False,
        "public_test_read": False,
        "synthetic_non_model_output": True,
        "capacity_target_count": len(capacity["records"]),
        "primary_pair_count": len(changed),
        "condition_count": len(prompts),
        "distinct_prompt_count": len(
            {sha256_text(value) for value in prompts.values()}
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare the PROPER v2 timeout paired model experiment."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--cpu-dry-run", action="store_true")
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()
    config = load_config(args.config)
    if args.cpu_dry_run:
        print(json.dumps(cpu_dry_run(config), indent=2, sort_keys=True))
        print("RESULT=PASS_PROPER_V2_TIMEOUT_PAIR_PREPARATION_DRY_RUN")
        return 0
    payload, _ = prepare_payload(args.config)
    write_prepared(payload, config)
    print(json.dumps(payload["screening"], indent=2, sort_keys=True))
    result = (
        "PASS_PROPER_V2_TIMEOUT_PAIR_PREPARATION"
        if payload["screening"]["ready_for_source_and_environment_lock"]
        else "STOP_PROPER_V2_TIMEOUT_PAIR_PREPARATION"
    )
    print(f"RESULT={result}")
    print("NOTE=No model was loaded and no model output was read or generated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
