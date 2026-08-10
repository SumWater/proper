from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Mapping

import yaml


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [
    str(ROOT / "src"),
    str(ROOT / "external" / "toolmisusebench"),
    str(ROOT / "experiments" / "proper_v1"),
    str(ROOT / "experiments" / "proper_v2"),
]

from agent_runtime import prepare_prefix  # noqa: E402
from benchmark_instances import (  # noqa: E402
    RETRY_POLICY,
    make_actual_instance,
    make_argument_omission_instance,
    policy_signature,
)
from confirmatory_gate_v1 import verify_test_file  # noqa: E402
from gate_dataset import (  # noqa: E402
    SAMPLE,
    as_experience,
    build_memory_sources,
    load_config as load_memory_config,
    load_exclusions,
    resolve_root_path,
)
from failure_memory.candidate_selector import (  # noqa: E402
    FailureFeatures,
    extract_failure_features,
)
from failure_memory.paper_2026 import (  # noqa: E402
    SelectorVariant,
    select_from_mappings,
)
from failure_memory.proper_v2 import (  # noqa: E402
    ObservableFailure,
    RetrySafety,
    RetrySafetyAssessment,
)
from failure_memory.retrieval import FailureQuery, SourceBlindTfidfRetriever  # noqa: E402
from timeout_capacity_v2 import policy_card, public_candidates  # noqa: E402
from toolmisusebench.dataset import load_tasks  # noqa: E402


CONFIG = ROOT / "configs" / "paper_2026" / "selector_capacity_audit_v0_1.yaml"
FORMAL_RUNTIME_CONFIG = (
    ROOT / "configs" / "proper_v1" / "confirmatory_gate_v1.runtime.yaml"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def root_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def canonical_sha256(value: Any) -> str:
    rendered = json.dumps(
        value, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if config.get("status") != "development_capacity_before_selector_freeze":
        raise RuntimeError("selector capacity audit config has invalid status")
    return config


def portable_windows_manifest_sha256(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    raw_sha = hashlib.sha256(raw).hexdigest()
    if b"\r\n" in raw:
        windows_bytes = raw
    else:
        windows_bytes = raw.replace(b"\n", b"\r\n")
    return raw_sha, hashlib.sha256(windows_bytes).hexdigest()


def rebuild_frozen_memory_bank(
    config: Mapping[str, Any], formal_config: Mapping[str, Any]
) -> tuple[list[Any], dict[str, Any], dict[str, Any]]:
    memory_config = config["memory_bank"]
    path = root_path(memory_config["prepared_manifest"])
    frozen = json.loads(path.read_text(encoding="utf-8"))
    raw_sha, windows_sha = portable_windows_manifest_sha256(path)
    expected_windows = str(memory_config["expected_windows_file_sha256"])
    if raw_sha != expected_windows and windows_sha != expected_windows:
        raise RuntimeError("memory-bank file differs beyond portable LF/CRLF serialization")
    if frozen["identities"]["prepared_payload_sha256"] != str(
        memory_config["expected_payload_sha256"]
    ):
        raise RuntimeError("memory-bank declared payload identity mismatch")

    dev_path = root_path(config["dataset"]["dev"])
    if sha256_file(dev_path) != str(config["dataset"]["dev_sha256"]):
        raise RuntimeError("frozen development dataset hash mismatch")
    historical_memory_config = load_memory_config()
    exclusion_path = resolve_root_path(historical_memory_config["pilot_exclusions"])
    exclusions, _ = load_exclusions(exclusion_path)
    tasks = load_tasks(SAMPLE, str(historical_memory_config["dataset"]["split"]))
    sources = build_memory_sources(tasks, historical_memory_config, exclusions)
    experiences = [as_experience(source) for source in sources]
    rebuilt = {
        item.experience_id: {
            "source_task_id": item.source_instance_id.split("::", 1)[0],
            "natural_text_sha256": hashlib.sha256(
                item.natural_text.encode("utf-8")
            ).hexdigest(),
        }
        for item in experiences
    }
    declared = {
        item["experience_id"]: {
            "source_task_id": item["source_task_id"],
            "natural_text_sha256": item["natural_text_sha256"],
        }
        for item in frozen["memory_sources"]
    }
    if rebuilt != declared:
        raise RuntimeError("rebuilt memory identities differ from frozen declaration")
    if len(sources) != int(memory_config["source_count"]):
        raise RuntimeError("unexpected frozen memory-bank source count")
    portability = {
        "path": str(memory_config["prepared_manifest"]),
        "raw_file_sha256": raw_sha,
        "windows_crlf_file_sha256": windows_sha,
        "expected_windows_file_sha256": expected_windows,
        "difference_class": (
            "none" if raw_sha == expected_windows else "lf_crlf_serialization_only"
        ),
        "payload_sha256": frozen["identities"]["prepared_payload_sha256"],
        "rebuilt_memory_identity_match": True,
    }
    return sources, frozen, portability


def evidence_codes(features: FailureFeatures) -> tuple[str, ...]:
    values = {
        f"failure_state:{features.state.value}",
    }
    if features.error_code:
        values.add(f"error_code:{features.error_code}")
    if features.error_code == "authz_denied" and features.repeated_same_call_count >= 2:
        values.add("persistent_authorization_denial")
    return tuple(sorted(values))


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
    public_evidence: list[str] = []
    satisfied: list[str] = []

    if retries_left <= 0:
        retry_status = RetrySafety.UNSAFE
        public_evidence.append("public_retry_budget:exhausted")
    elif features.error_code == "missing_required_arg" and features.missing_fields:
        retry_status = RetrySafety.UNSAFE
        public_evidence.append("public_error:missing_required_argument")
    elif features.error_code == "timeout" and retries_left > 0:
        retry_status = RetrySafety.SAFE
        public_evidence.extend(
            ["public_error:timeout", "public_retry_budget:positive"]
        )
        satisfied.append("retry_budget_available")
    elif (
        features.error_code == "authz_denied"
        and features.repeated_same_call_count == 1
        and retries_left > 0
    ):
        retry_status = RetrySafety.SAFE
        public_evidence.extend(
            [
                "public_error:authorization_denied_before_execution",
                "public_first_denial",
                "public_retry_budget:positive",
            ]
        )
        satisfied.append("retry_budget_available")
    else:
        retry_status = RetrySafety.UNKNOWN

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
        available_capabilities=(
            ("bounded_same_action_retry",) if retries_left > 0 else ()
        ),
        satisfied_facts=tuple(satisfied),
        violated_facts=(),
        repeated_same_call_count=features.repeated_same_call_count,
        retry_safety=RetrySafetyAssessment(retry_status, tuple(public_evidence)),
    )


def load_cohort_records(config: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    cohorts: dict[str, list[dict[str, Any]]] = {}
    for stratum, spec in config["cohorts"].items():
        path = root_path(spec["context"])
        payload = json.loads(path.read_text(encoding="utf-8"))
        records = payload["records"]
        if len(records) != int(spec["expected_count"]):
            raise RuntimeError(f"unexpected frozen cohort count: {stratum}")
        cohorts[str(stratum)] = records
    return cohorts


def build_instance(
    stratum: str, task: Any
) -> Any:
    builders: dict[str, Callable[[Any], Any]] = {
        "argument_omission": make_argument_omission_instance,
        "transient_authorization": lambda value: make_actual_instance(
            value, "authorization_transient", RETRY_POLICY
        ),
        "timeout": lambda value: make_actual_instance(
            value, "timeout_transient", RETRY_POLICY
        ),
    }
    return builders[stratum](task)


def summarize_variant(records: list[dict[str, Any]], variant: str) -> dict[str, Any]:
    decisions = [item["decisions"][variant] for item in records]
    changed = [value for value in decisions if value["selection_changed"]]
    selected = Counter(value["selected_experience_id"] for value in changed)
    actions = Counter(value["action"] for value in decisions)
    maximum = max(selected.values(), default=0)
    selected_applicable = [
        bool(item["evaluator_only"]["selected_policy_applicable"][variant])
        for item in records
    ]
    changed_records = [
        item for item in records if item["decisions"][variant]["selection_changed"]
    ]
    changed_selected_applicable = sum(
        bool(item["evaluator_only"]["selected_policy_applicable"][variant])
        for item in changed_records
    )
    corrections = sum(
        not bool(item["evaluator_only"]["rank1_policy_applicable"])
        and bool(item["evaluator_only"]["selected_policy_applicable"][variant])
        for item in records
    )
    new_errors = sum(
        bool(item["evaluator_only"]["rank1_policy_applicable"])
        and not bool(item["evaluator_only"]["selected_policy_applicable"][variant])
        for item in records
    )
    active_contradicted = 0
    for item in records:
        decision = item["decisions"][variant]
        if decision["action"] != "select":
            continue
        selected_evaluation = next(
            value
            for value in decision["candidate_evaluations"]
            if value["experience_id"] == decision["selected_experience_id"]
        )
        active_contradicted += bool(selected_evaluation["observed_contradictions"])
    return {
        "target_count": len(records),
        "selection_changed_from_tfidf_count": len(changed),
        "selection_changed_from_tfidf_rate": len(changed) / len(records),
        "action_counts": dict(sorted(actions.items())),
        "distinct_changed_target_tool_count": len(
            {
                item["target_tool_name"]
                for item in records
                if item["decisions"][variant]["selection_changed"]
            }
        ),
        "distinct_selected_memory_count_on_changed_targets": len(selected),
        "maximum_single_selected_memory_count": maximum,
        "maximum_single_selected_memory_share": (
            maximum / len(changed) if changed else 0.0
        ),
        "evaluator_only_selected_policy_applicable_count": sum(selected_applicable),
        "evaluator_only_selected_policy_applicable_rate": (
            sum(selected_applicable) / len(records)
        ),
        "evaluator_only_changed_selection_applicable_count": changed_selected_applicable,
        "evaluator_only_changed_selection_applicable_rate": (
            changed_selected_applicable / len(changed_records)
            if changed_records
            else 0.0
        ),
        "evaluator_only_rank1_errors_corrected_count": corrections,
        "evaluator_only_new_errors_from_rank1_count": new_errors,
        "active_selection_with_observed_contradiction_count": active_contradicted,
    }


def summarize(records: list[dict[str, Any]], variants: list[str]) -> dict[str, Any]:
    by_stratum: dict[str, Any] = {}
    for stratum in sorted({item["stratum"] for item in records}):
        selected_records = [item for item in records if item["stratum"] == stratum]
        entry = {
            variant: summarize_variant(selected_records, variant)
            for variant in variants
        }
        proper_ids = {
            item["instance_id"]: item["decisions"]["proper"]["selected_experience_id"]
            for item in selected_records
        }
        for ablation in ("proper_no_gate", "proper_no_contradiction"):
            entry[ablation]["different_from_full_proper_count"] = sum(
                item["decisions"][ablation]["selected_experience_id"]
                != proper_ids[item["instance_id"]]
                for item in selected_records
            )
        entry["changed_target_union_across_variants_count"] = sum(
            any(
                item["decisions"][variant]["selection_changed"]
                for variant in variants
            )
            for item in selected_records
        )
        by_stratum[stratum] = entry

    overall = {variant: summarize_variant(records, variant) for variant in variants}
    for ablation in ("proper_no_gate", "proper_no_contradiction"):
        overall[ablation]["different_from_full_proper_count"] = sum(
            item["decisions"][ablation]["selected_experience_id"]
            != item["decisions"]["proper"]["selected_experience_id"]
            for item in records
        )
    return {
        "by_stratum": by_stratum,
        "overall": overall,
        "changed_target_union_across_variants_count": sum(
            any(
                item["decisions"][variant]["selection_changed"]
                for variant in variants
            )
            for item in records
        ),
        "rank1_policy_inapplicable_count": sum(
            not bool(item["evaluator_only"]["rank1_policy_applicable"])
            for item in records
        ),
    }


def run_audit(
    config_path: Path = CONFIG, *, limit_per_stratum: int | None = None
) -> dict[str, Any]:
    config = load_config(config_path)
    formal_config = yaml.safe_load(FORMAL_RUNTIME_CONFIG.read_text(encoding="utf-8"))
    public_test = verify_test_file(formal_config)
    if sha256_file(public_test) != str(config["dataset"]["public_test_sha256"]):
        raise RuntimeError("public-test dataset identity mismatch")
    tasks = load_tasks(public_test.parent, str(formal_config["dataset"]["split"]))
    if len(tasks) != int(config["dataset"]["expected_task_count"]):
        raise RuntimeError("unexpected public-test task count")
    task_by_id = {task.task_id: task for task in tasks}

    sources, frozen_memory, portability = rebuild_frozen_memory_bank(
        config, formal_config
    )
    experiences = [as_experience(source) for source in sources]
    experience_by_id = {item.experience_id: item for item in experiences}
    source_observations = {
        f"experience::{source.instance_id}": prepare_prefix(source)[1]
        for source in sources
    }
    retriever = SourceBlindTfidfRetriever(experiences)
    cohorts = load_cohort_records(config)
    variants = [str(value) for value in config["selector"]["variants"]]
    threshold = float(config["selector"]["minimum_extraction_confidence"])
    top_k = int(config["memory_bank"]["top_k"])

    records: list[dict[str, Any]] = []
    for stratum, frozen_records in cohorts.items():
        selected_records = (
            frozen_records[:limit_per_stratum]
            if limit_per_stratum is not None
            else frozen_records
        )
        for frozen_record in selected_records:
            source_task_id = str(frozen_record["source_task_id"])
            task = task_by_id.get(source_task_id)
            if task is None:
                raise RuntimeError(f"frozen target is absent from public test: {source_task_id}")
            instance = build_instance(stratum, task)
            if instance is None or instance.instance_id != frozen_record["instance_id"]:
                raise RuntimeError(f"frozen target failed reconstruction: {source_task_id}")
            ranked = retriever.retrieve(
                FailureQuery(instance.instance_id, instance.query_text, instance.provenance),
                top_k=top_k,
            )
            _, visible, prefix_sha256 = prepare_prefix(instance)
            if prefix_sha256 != frozen_record["prefix_sha256"]:
                raise RuntimeError(f"observable prefix hash mismatch: {instance.instance_id}")
            features = extract_failure_features(visible)
            candidates = public_candidates(
                ranked=ranked,
                experience_by_id=experience_by_id,
                source_observations=source_observations,
            )
            cards = [policy_card(candidate) for candidate in candidates]
            target = observable_failure(visible, features)
            decisions = {
                variant: select_from_mappings(
                    target.to_mapping(),
                    [card.to_mapping() for card in cards],
                    variant=SelectorVariant(variant),
                    minimum_extraction_confidence=threshold,
                ).to_mapping()
                for variant in variants
            }
            rank1_experience = experience_by_id[cards[0].experience_id]
            selected_applicability = {
                variant: bool(
                    instance.applicability[
                        policy_signature(
                            experience_by_id[
                                decisions[variant]["selected_experience_id"]
                            ].policy
                        )
                    ]
                )
                for variant in variants
            }
            records.append(
                {
                    "stratum": stratum,
                    "instance_id": instance.instance_id,
                    "source_task_id": source_task_id,
                    "prefix_sha256": prefix_sha256,
                    "target_tool_name": features.tool_name,
                    "target_state_sha256": canonical_sha256(target.to_mapping()),
                    "rank1_experience_id": cards[0].experience_id,
                    "candidate_identity_sha256": canonical_sha256(
                        [
                            {
                                "experience_id": card.experience_id,
                                "original_rank": card.original_rank,
                                "retrieval_score": card.retrieval_score,
                            }
                            for card in cards
                        ]
                    ),
                    "decisions": decisions,
                    "evaluator_only": {
                        "rank1_policy_applicable": bool(
                            instance.applicability[
                                policy_signature(rank1_experience.policy)
                            ]
                        ),
                        "selected_policy_applicable": selected_applicability,
                    },
                }
            )

    expected_total = sum(int(value["expected_count"]) for value in config["cohorts"].values())
    if limit_per_stratum is None and len(records) != expected_total:
        raise RuntimeError("complete capacity audit target count mismatch")
    return {
        "schema_version": 1,
        "run_kind": "paper_2026_three_stratum_selector_capacity_audit",
        "status": "complete" if limit_per_stratum is None else "development_sample",
        "identities": {
            "config_sha256": sha256_file(config_path),
            "runner_sha256": sha256_file(Path(__file__).resolve()),
            "dev_sha256": sha256_file(root_path(config["dataset"]["dev"])),
            "public_test_sha256": sha256_file(public_test),
            "memory_bank": portability,
        },
        "boundary": {
            "model_loaded": False,
            "model_outputs_read_or_generated": False,
            "cohort_labels_used_evaluator_side_only": True,
            "selector_inputs_observable_only": True,
        },
        "summary": summarize(records, variants),
        "records": records,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the model-free three-stratum paper selector capacity audit."
    )
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--limit-per-stratum", type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.limit_per_stratum is not None and args.limit_per_stratum < 1:
        raise ValueError("limit-per-stratum must be positive")
    payload = run_audit(
        args.config.resolve(), limit_per_stratum=args.limit_per_stratum
    )
    config = load_config(args.config.resolve())
    output = args.output or root_path(config["output"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    print(f"OUTPUT={output}")
    print("NOTE=No model was loaded and no model output was read or generated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
