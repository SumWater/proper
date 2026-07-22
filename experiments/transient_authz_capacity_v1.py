from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "external" / "toolmisusebench"))

from agent_runtime import prepare_prefix  # noqa: E402
from benchmark_instances import RETRY_POLICY, make_actual_instance  # noqa: E402
from candidate_manifest import candidate_payload, failure_payload  # noqa: E402
from confirmatory_gate_v1 import frozen_memory_bank, verify_test_file  # noqa: E402
from gate_dataset import as_experience, task_fault  # noqa: E402
from failure_memory.candidate_selector import (  # noqa: E402
    extract_candidate_features,
    extract_failure_features,
)
from failure_memory.retrieval import FailureQuery, SourceBlindTfidfRetriever  # noqa: E402
from failure_memory.transient_authz_gate import (  # noqa: E402
    TransientAuthzCandidate,
    select_for_features,
    select_transient_authz_memory,
)
from toolmisusebench.dataset import load_tasks  # noqa: E402


CONFIG = ROOT / "configs" / "transient_authz_capacity_v1.yaml"
FORMAL_RUNTIME_CONFIG = ROOT / "configs" / "confirmatory_gate_v1.runtime.yaml"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if config.get("status") != "frozen_cpu_capacity_protocol_before_native_authz_model_outputs":
        raise RuntimeError("transient-authz capacity configuration has invalid status")
    return config


def prior_source_task_ids(config: Mapping[str, Any]) -> set[str]:
    value = config["prior_result_exclusion"]
    path = ROOT / value["result"]
    if sha256_file(path) != str(value["result_sha256"]):
        raise RuntimeError("prior confirmatory result hash mismatch")
    result = json.loads(path.read_text(encoding="utf-8"))
    source_ids = {str(item["source_task_id"]) for item in result["records"]}
    if len(source_ids) != int(value["expected_source_task_count"]):
        raise RuntimeError("unexpected prior source-task exclusion count")
    return source_ids


def public_candidates(
    *,
    ranked: list[Any],
    experience_by_id: Mapping[str, Any],
    source_observations: Mapping[str, Any],
) -> list[Any]:
    return [
        extract_candidate_features(
            experience_id=item.experience.experience_id,
            natural_text=experience_by_id[item.experience.experience_id].natural_text,
            original_rank=item.rank,
            tfidf_score=round(item.score, 12),
            source_observation=source_observations[item.experience.experience_id],
        )
        for item in ranked
    ]


def summarize_records(records: list[dict[str, Any]], config: Mapping[str, Any]) -> dict[str, Any]:
    changed = [item for item in records if item["selection_changed"]]
    selected_counts = Counter(item["selected_experience_id"] for item in changed)
    maximum = max(selected_counts.values(), default=0)
    distinct_changed_tools = len({item["target_tool_name"] for item in changed})
    maximum_share = maximum / len(changed) if changed else 0.0
    gate = config["capacity_gate"]
    checks = {
        "valid_native_target_capacity_met": len(records)
        >= int(gate["minimum_valid_native_targets"]),
        "selection_changed_capacity_met": len(changed)
        >= int(gate["minimum_selection_changed_pairs"]),
        "changed_tool_diversity_met": distinct_changed_tools
        >= int(gate["minimum_changed_pair_distinct_tools"]),
        "selected_memory_diversity_met": len(selected_counts)
        >= int(gate["minimum_selected_memory_count"]),
        "memory_concentration_limit_met": maximum_share
        <= float(gate["maximum_single_selected_memory_share"]),
    }
    return {
        "valid_native_target_count": len(records),
        "selection_changed_count": len(changed),
        "preferred_selection_changed_count": int(
            gate["preferred_selection_changed_pairs"]
        ),
        "preferred_selection_changed_capacity_met": len(changed)
        >= int(gate["preferred_selection_changed_pairs"]),
        "distinct_target_tool_count": len(
            {item["target_tool_name"] for item in records}
        ),
        "distinct_changed_target_tool_count": distinct_changed_tools,
        "distinct_selected_memory_count_on_changed_pairs": len(selected_counts),
        "maximum_single_selected_memory_count": maximum,
        "maximum_single_selected_memory_share": maximum_share,
        "capacity_checks": checks,
        "future_protocol_preparation_authorized": all(checks.values()),
        "gpu_run_authorized": False,
    }


def prepare(config_path: Path = CONFIG) -> dict[str, Any]:
    config = load_config(config_path)
    formal_config = yaml.safe_load(FORMAL_RUNTIME_CONFIG.read_text(encoding="utf-8"))
    formal_dependencies = formal_config["development_dependencies"]
    if str(config["memory_bank"]["prepared_manifest_sha256"]) != str(
        formal_dependencies["frozen_memory_bank_manifest_sha256"]
    ):
        raise RuntimeError("capacity config and formal runtime disagree on memory manifest")
    if str(config["memory_bank"]["dev_sample_sha256"]) != str(
        formal_dependencies["dev_sample_sha256"]
    ):
        raise RuntimeError("capacity config and formal runtime disagree on dev sample")
    public_test = verify_test_file(formal_config)
    if sha256_file(public_test) != str(config["dataset"]["sha256"]):
        raise RuntimeError("capacity config and formal runtime disagree on public-test hash")
    tasks = load_tasks(public_test.parent, str(config["dataset"]["split"]))
    if len(tasks) != int(config["dataset"]["expected_task_count"]):
        raise RuntimeError("unexpected public-test task count")
    excluded = prior_source_task_ids(config)

    sources, frozen_memory = frozen_memory_bank(formal_config)
    if len(sources) != int(config["memory_bank"]["source_count"]):
        raise RuntimeError("unexpected frozen memory-bank size")
    experiences = [as_experience(source) for source in sources]
    source_task_ids = {source.source_task_id for source in sources}
    experience_by_id = {item.experience_id: item for item in experiences}
    source_observations = {
        f"experience::{source.instance_id}": prepare_prefix(source)[1]
        for source in sources
    }
    retriever = SourceBlindTfidfRetriever(experiences)

    native_tasks = [task for task in tasks if task_fault(task) == "authz"]
    exact_prior_overlap = sum(task.task_id in excluded for task in native_tasks)
    eligible_tasks = [task for task in native_tasks if task.task_id not in excluded]
    source_target_overlap = source_task_ids & {task.task_id for task in eligible_tasks}
    if source_target_overlap:
        raise RuntimeError("dev memory sources overlap public-test targets")
    records: list[dict[str, Any]] = []
    rejected = 0
    no_retry_top10 = 0
    top_k = int(config["memory_bank"]["top_k"])
    for task in eligible_tasks:
        instance = make_actual_instance(task, "authorization_transient", RETRY_POLICY)
        if instance is None:
            rejected += 1
            continue
        ranked = retriever.retrieve(
            FailureQuery(instance.instance_id, instance.query_text, instance.provenance),
            top_k=top_k,
        )
        _, visible, prefix_sha256 = prepare_prefix(instance)
        features = extract_failure_features(visible)
        candidates = public_candidates(
            ranked=ranked,
            experience_by_id=experience_by_id,
            source_observations=source_observations,
        )
        selector_candidates = [
            TransientAuthzCandidate(
                experience_id=item.experience_id,
                original_rank=item.original_rank,
                policy=item.policy,
                source_tool_name=item.source_failure.tool_name,
            )
            for item in candidates
        ]
        try:
            decision = select_for_features(features, selector_candidates)
        except ValueError as exc:
            if "no retry memory" not in str(exc):
                raise
            no_retry_top10 += 1
            continue
        rank1 = min(candidates, key=lambda item: item.original_rank)
        records.append(
            {
                "instance_id": instance.instance_id,
                "source_task_id": instance.source_task_id,
                "prefix_sha256": prefix_sha256,
                "target_tool_name": features.tool_name,
                "target_features": failure_payload(features),
                "rank1_experience_id": rank1.experience_id,
                "rank1_policy": rank1.policy.value,
                "selected_experience_id": decision.selected_experience_id,
                "selected_original_rank": decision.selected_original_rank,
                "selected_same_tool_memory": decision.same_tool_memory,
                "selection_changed": decision.selection_changed,
                "selection_reason_code": decision.reason_code,
                "top10_candidates": [candidate_payload(item) for item in candidates],
            }
        )

    screening = summarize_records(records, config)
    screening.update(
        {
            "public_test_task_count": len(tasks),
            "native_authz_task_count": len(native_tasks),
            "prior_source_task_exclusion_count": len(excluded),
            "native_authz_exact_prior_overlap_count": exact_prior_overlap,
            "memory_source_target_overlap_count": len(source_target_overlap),
            "eligible_native_authz_task_count": len(eligible_tasks),
            "rejected_native_authz_task_count": rejected,
            "no_retry_memory_in_top10_count": no_retry_top10,
        }
    )
    return {
        "schema_version": 1,
        "run_kind": "transient_authz_public_test_capacity_screening",
        "identities": {
            "config_sha256": sha256_file(config_path),
            "public_test_sha256": sha256_file(public_test),
            "prior_result_sha256": sha256_file(
                ROOT / config["prior_result_exclusion"]["result"]
            ),
            "frozen_memory_bank_manifest_sha256": sha256_file(
                ROOT / config["memory_bank"]["prepared_manifest"]
            ),
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
            "cohort_fault_label_used_evaluator_side_only": True,
            "gpu_run_authorized": False,
        },
        "screening": screening,
        "records": records,
    }


def synthetic_observation() -> dict[str, Any]:
    failed = {
        "tool_name": "read_file",
        "args": {"path": "/visible/example"},
        "error": {"code": "authz_denied", "message": "Denied", "details": {}},
        "output": None,
    }
    return {
        "last_error": failed["error"],
        "tool_schemas": [
            {
                "name": "read_file",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
                "additionalProperties": False,
            }
        ],
        "transcript": [failed],
    }


def cpu_dry_run() -> dict[str, Any]:
    candidates = [
        TransientAuthzCandidate.from_public_mapping(
            {
                "experience_id": "stop-memory",
                "original_rank": 1,
                "policy_from_text": "stop",
                "source_failure": {"tool_name": "read_file"},
            }
        ),
        TransientAuthzCandidate.from_public_mapping(
            {
                "experience_id": "retry-memory",
                "original_rank": 2,
                "policy_from_text": "retry",
                "source_failure": {"tool_name": "read_file"},
            }
        ),
    ]
    decision = select_transient_authz_memory(synthetic_observation(), candidates)
    return {
        "model_loaded": False,
        "public_test_read": False,
        "synthetic_non_model_output": True,
        "decision": asdict(decision),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit native transient-authz capacity.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--cpu-dry-run", action="store_true")
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.cpu_dry_run:
        print(json.dumps(cpu_dry_run(), indent=2, sort_keys=True, default=str))
        print("RESULT=PASS_TRANSIENT_AUTHZ_CAPACITY_CPU_DRY_RUN")
        return 0
    config = load_config(args.config)
    payload = prepare(args.config)
    output = args.output or ROOT / config["outputs"]["screening"]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload["screening"], indent=2, sort_keys=True))
    result = (
        "PASS_TRANSIENT_AUTHZ_PUBLIC_TEST_CAPACITY"
        if payload["screening"]["future_protocol_preparation_authorized"]
        else "STOP_TRANSIENT_AUTHZ_PUBLIC_TEST_CAPACITY"
    )
    print(f"RESULT={result}")
    print("NOTE=No model was loaded and no model output was read or generated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
