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


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "external" / "toolmisusebench"))
sys.path.insert(0, str(ROOT / "experiments" / "proper_v1"))

from agent_runtime import prepare_prefix  # noqa: E402
from benchmark_instances import RETRY_POLICY, make_actual_instance  # noqa: E402
from confirmatory_gate_v1 import frozen_memory_bank, verify_test_file  # noqa: E402
from gate_dataset import as_experience, resolve_root_path, task_fault  # noqa: E402
from failure_memory.candidate_selector import (  # noqa: E402
    CandidateFeatures,
    FailureFeatures,
    PolicyClass,
    extract_candidate_features,
    extract_failure_features,
)
from failure_memory.proper_v2 import (  # noqa: E402
    ContinuationPolicy,
    MemoryPolicyCard,
    ObservableFailure,
    RecoveryOperation,
    RetrySafety,
    RetrySafetyAssessment,
    load_policy_cards,
    select_memory,
)
from failure_memory.retrieval import FailureQuery, SourceBlindTfidfRetriever  # noqa: E402
from toolmisusebench.dataset import load_tasks  # noqa: E402


CONFIG = ROOT / "configs" / "proper_v2" / "timeout_capacity_v2.yaml"
FORMAL_RUNTIME_CONFIG = (
    ROOT / "configs" / "proper_v1" / "confirmatory_gate_v1.runtime.yaml"
)
PUBLIC_TIMEOUT_CONTRACT = (
    "public_contract:timeout_before_tool_execution_without_side_effect"
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if config.get("status") != "development_cpu_capacity_before_timeout_model_outputs":
        raise RuntimeError("timeout capacity configuration has invalid status")
    return config


def prior_source_task_ids(
    config: Mapping[str, Any],
) -> tuple[set[str], dict[str, int]]:
    combined: set[str] = set()
    counts: dict[str, int] = {}
    for value in config["prior_result_exclusions"]:
        path = resolve_root_path(value["result"])
        if sha256_file(path) != str(value["result_sha256"]):
            raise RuntimeError(f"prior result hash mismatch: {value['name']}")
        result = json.loads(path.read_text(encoding="utf-8"))
        source_ids = {str(item["source_task_id"]) for item in result["records"]}
        if len(source_ids) != int(value["expected_source_task_count"]):
            raise RuntimeError(f"unexpected prior source-task count: {value['name']}")
        counts[str(value["name"])] = len(source_ids)
        combined.update(source_ids)
    return combined, counts


def evidence_codes(features: FailureFeatures) -> tuple[str, ...]:
    values = {f"failure_state:{features.state.value}"}
    if features.error_code:
        values.add(f"error_code:{features.error_code}")
    return tuple(sorted(values))


def policy_card(candidate: CandidateFeatures) -> MemoryPolicyCard:
    policy = candidate.policy
    operation = {
        PolicyClass.RETRY: RecoveryOperation.RETRY_SAME_ACTION,
        PolicyClass.REPAIR: RecoveryOperation.REPAIR_ARGUMENTS,
        PolicyClass.STOP: RecoveryOperation.STOP_AND_REPORT,
        PolicyClass.UNKNOWN: RecoveryOperation.UNKNOWN,
    }[policy]
    continuation = {
        PolicyClass.RETRY: ContinuationPolicy.RETRY_THEN_VERIFY,
        PolicyClass.REPAIR: ContinuationPolicy.VERIFY_THEN_CONTINUE,
        PolicyClass.STOP: ContinuationPolicy.TERMINATE,
        PolicyClass.UNKNOWN: ContinuationPolicy.UNKNOWN,
    }[policy]
    stop_conditions = (
        ("persistent_authorization_denial",) if policy == PolicyClass.STOP else ()
    )
    return MemoryPolicyCard(
        experience_id=candidate.experience_id,
        natural_text=candidate.natural_text,
        original_rank=candidate.original_rank,
        retrieval_score=candidate.tfidf_score,
        trigger_evidence=evidence_codes(candidate.source_failure),
        required_preconditions=(),
        recovery_operation=operation,
        target_object=candidate.source_failure.tool_name,
        proposed_action=None,
        repair_targets=candidate.repair_targets,
        continuation_policy=continuation,
        success_evidence=("tool_succeeds",),
        stop_conditions=stop_conditions,
        source_tool=candidate.source_failure.tool_name,
        extraction_confidence=1.0,
    )


def observable_failure(
    visible: Mapping[str, Any], features: FailureFeatures
) -> ObservableFailure:
    schemas = visible.get("tool_schemas", [])
    available_tools = tuple(
        sorted(
            str(item["name"])
            for item in schemas
            if isinstance(item, Mapping) and item.get("name")
        )
    )
    remaining = visible.get("remaining_budget") or {}
    retries_left = int(remaining.get("retries_left", 0))
    retry_safe = features.error_code == "timeout" and retries_left > 0
    retry_evidence = (
        (
            "public_error:timeout",
            "public_retry_budget:positive",
            PUBLIC_TIMEOUT_CONTRACT,
        )
        if retry_safe
        else ()
    )
    return ObservableFailure(
        instruction=str(visible.get("instruction", "")),
        tool_name=features.tool_name,
        failed_arguments=features.failed_arguments,
        error_code=features.error_code,
        evidence_codes=evidence_codes(features),
        failed_argument_paths=features.failed_argument_paths,
        missing_fields=features.missing_fields,
        public_schema_fields=features.public_schema_fields,
        public_required_fields=features.public_required_fields,
        available_tools=available_tools,
        available_capabilities=("bounded_same_action_retry",),
        satisfied_facts=(
            (PUBLIC_TIMEOUT_CONTRACT, "retry_budget_available")
            if retry_safe
            else ()
        ),
        violated_facts=(),
        repeated_same_call_count=features.repeated_same_call_count,
        retry_safety=RetrySafetyAssessment(
            RetrySafety.SAFE if retry_safe else RetrySafety.UNKNOWN,
            retry_evidence,
        ),
    )


def public_candidates(
    *,
    ranked: list[Any],
    experience_by_id: Mapping[str, Any],
    source_observations: Mapping[str, Any],
) -> list[CandidateFeatures]:
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


def summarize_records(
    records: list[dict[str, Any]], config: Mapping[str, Any]
) -> dict[str, Any]:
    changed = [item for item in records if item["selection_changed"]]
    selected_counts = Counter(item["selected_experience_id"] for item in changed)
    maximum = max(selected_counts.values(), default=0)
    maximum_share = maximum / len(changed) if changed else 0.0
    changed_tools = {item["target_tool_name"] for item in changed}
    gate = config["capacity_gate"]
    checks = {
        "valid_native_target_capacity_met": len(records)
        >= int(gate["minimum_valid_native_targets"]),
        "selection_changed_capacity_met": len(changed)
        >= int(gate["minimum_selection_changed_pairs"]),
        "changed_tool_diversity_met": len(changed_tools)
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
        "distinct_changed_target_tool_count": len(changed_tools),
        "distinct_selected_memory_count_on_changed_pairs": len(selected_counts),
        "maximum_single_selected_memory_count": maximum,
        "maximum_single_selected_memory_share": maximum_share,
        "selected_memory_counts_on_changed_pairs": dict(
            sorted(selected_counts.items())
        ),
        "capacity_checks": checks,
        "future_protocol_preparation_authorized": all(checks.values()),
        "gpu_run_authorized": False,
    }


def prepare(config_path: Path = CONFIG) -> dict[str, Any]:
    config = load_config(config_path)
    formal_config = yaml.safe_load(FORMAL_RUNTIME_CONFIG.read_text(encoding="utf-8"))
    public_test = verify_test_file(formal_config)
    if sha256_file(public_test) != str(config["dataset"]["sha256"]):
        raise RuntimeError("public-test hash mismatch")
    tasks = load_tasks(public_test.parent, str(config["dataset"]["split"]))
    if len(tasks) != int(config["dataset"]["expected_task_count"]):
        raise RuntimeError("unexpected public-test task count")
    excluded, exclusion_counts = prior_source_task_ids(config)

    sources, frozen_memory = frozen_memory_bank(formal_config)
    if len(sources) != int(config["memory_bank"]["source_count"]):
        raise RuntimeError("unexpected frozen memory-bank size")
    experiences = [as_experience(source) for source in sources]
    experience_by_id = {item.experience_id: item for item in experiences}
    source_task_ids = {source.source_task_id for source in sources}
    source_observations = {
        f"experience::{source.instance_id}": prepare_prefix(source)[1]
        for source in sources
    }
    retriever = SourceBlindTfidfRetriever(experiences)

    native_tasks = [task for task in tasks if task_fault(task) == "timeout"]
    exact_prior_overlap = sum(task.task_id in excluded for task in native_tasks)
    eligible_tasks = [task for task in native_tasks if task.task_id not in excluded]
    overlap = source_task_ids & {task.task_id for task in eligible_tasks}
    if overlap:
        raise RuntimeError("dev memory sources overlap public-test targets")

    records: list[dict[str, Any]] = []
    rejected = 0
    top_k = int(config["memory_bank"]["top_k"])
    threshold = float(config["selector"]["minimum_extraction_confidence"])
    for task in eligible_tasks:
        instance = make_actual_instance(task, "timeout_transient", RETRY_POLICY)
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
        cards = load_policy_cards(
            [policy_card(candidate).to_mapping() for candidate in candidates]
        )
        target = observable_failure(visible, features)
        decision = select_memory(
            target,
            cards,
            minimum_extraction_confidence=threshold,
        )
        rank1 = min(cards, key=lambda item: item.original_rank)
        selected = next(
            item for item in cards if item.experience_id == decision.selected_experience_id
        )
        records.append(
            {
                "instance_id": instance.instance_id,
                "source_task_id": instance.source_task_id,
                "prefix_sha256": prefix_sha256,
                "target_tool_name": features.tool_name,
                "rank1_experience_id": rank1.experience_id,
                "rank1_operation": rank1.recovery_operation.value,
                "selected_experience_id": selected.experience_id,
                "selected_original_rank": selected.original_rank,
                "selected_operation": selected.recovery_operation.value,
                "selection_changed": decision.selection_changed,
                "abstained": decision.abstained,
                "selection_reason_codes": list(decision.reason_codes),
                "selection_decision": decision.to_mapping(),
            }
        )

    screening = summarize_records(records, config)
    screening.update(
        {
            "public_test_task_count": len(tasks),
            "native_timeout_task_count": len(native_tasks),
            "prior_exclusion_source_task_counts": exclusion_counts,
            "prior_exclusion_union_count": len(excluded),
            "native_timeout_exact_prior_overlap_count": exact_prior_overlap,
            "eligible_native_timeout_task_count": len(eligible_tasks),
            "rejected_native_timeout_task_count": rejected,
            "memory_source_target_overlap_count": len(overlap),
        }
    )
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_timeout_public_test_capacity_screening",
        "identities": {
            "config_sha256": sha256_file(config_path),
            "public_test_sha256": sha256_file(public_test),
            "frozen_memory_bank_manifest_sha256": sha256_file(
                resolve_root_path(config["memory_bank"]["prepared_manifest"])
            ),
            "frozen_memory_bank_payload_sha256": frozen_memory["identities"][
                "prepared_payload_sha256"
            ],
            "prior_result_sha256": {
                str(value["name"]): sha256_file(resolve_root_path(value["result"]))
                for value in config["prior_result_exclusions"]
            },
        },
        "boundary": {
            "released_native_timeout_only": True,
            "all_prior_used_base_tasks_excluded": True,
            "model_loaded": False,
            "model_outputs_read": False,
            "selector_hidden_labels_used": False,
            "cohort_fault_label_used_evaluator_side_only": True,
            "public_timeout_contract_used": PUBLIC_TIMEOUT_CONTRACT,
            "gpu_run_authorized": False,
        },
        "screening": screening,
        "records": records,
    }


def synthetic_target() -> ObservableFailure:
    return ObservableFailure(
        instruction="Read a file.",
        tool_name="read_file",
        failed_arguments={"path": "/visible/example"},
        error_code="timeout",
        evidence_codes=("error_code:timeout", "failure_state:timeout"),
        failed_argument_paths=("/path",),
        missing_fields=(),
        public_schema_fields=("path",),
        public_required_fields=("path",),
        available_tools=("read_file",),
        available_capabilities=("bounded_same_action_retry",),
        satisfied_facts=(PUBLIC_TIMEOUT_CONTRACT, "retry_budget_available"),
        violated_facts=(),
        repeated_same_call_count=1,
        retry_safety=RetrySafetyAssessment(
            RetrySafety.SAFE,
            (
                "public_error:timeout",
                "public_retry_budget:positive",
                PUBLIC_TIMEOUT_CONTRACT,
            ),
        ),
    )


def synthetic_cards() -> tuple[MemoryPolicyCard, ...]:
    payloads = []
    for experience_id, rank, operation, trigger, continuation, stop in (
        (
            "stop-memory",
            1,
            "stop_and_report",
            ["error_code:authz_denied"],
            "terminate",
            ["persistent_authorization_denial"],
        ),
        (
            "retry-memory",
            2,
            "retry_same_action",
            ["error_code:timeout", "failure_state:timeout"],
            "retry_then_verify",
            [],
        ),
    ):
        payloads.append(
            {
                "schema_version": 1,
                "experience_id": experience_id,
                "natural_text": experience_id,
                "original_rank": rank,
                "retrieval_score": 1.0 / rank,
                "trigger_evidence": trigger,
                "required_preconditions": [],
                "recovery_operation": operation,
                "target_object": "read_file",
                "proposed_action": None,
                "repair_targets": [],
                "continuation_policy": continuation,
                "success_evidence": ["tool_succeeds"],
                "stop_conditions": stop,
                "source_tool": "read_file",
                "extraction_confidence": 1.0,
            }
        )
    return load_policy_cards(payloads)


def cpu_dry_run() -> dict[str, Any]:
    decision = select_memory(synthetic_target(), synthetic_cards())
    return {
        "model_loaded": False,
        "public_test_read": False,
        "synthetic_non_model_output": True,
        "decision": decision.to_mapping(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit PROPER v2 timeout capacity.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--cpu-dry-run", action="store_true")
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.cpu_dry_run:
        print(json.dumps(cpu_dry_run(), indent=2, sort_keys=True))
        print("RESULT=PASS_PROPER_V2_TIMEOUT_CAPACITY_CPU_DRY_RUN")
        return 0
    config = load_config(args.config)
    payload = prepare(args.config)
    output = args.output or resolve_root_path(config["outputs"]["screening"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["screening"], indent=2, sort_keys=True))
    result = (
        "PASS_PROPER_V2_TIMEOUT_PUBLIC_TEST_CAPACITY"
        if payload["screening"]["future_protocol_preparation_authorized"]
        else "STOP_PROPER_V2_TIMEOUT_PUBLIC_TEST_CAPACITY"
    )
    print(f"RESULT={result}")
    print("NOTE=No model was loaded and no model output was read or generated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
