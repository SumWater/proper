from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "external" / "toolmisusebench"))

from agent_runtime import build_prompt, prepare_prefix, sha256_file, sha256_text  # noqa: E402
from gate_dataset import (  # noqa: E402
    SAMPLE,
    as_experience,
    build_memory_sources,
    build_targets,
    load_config as load_confirmatory_config,
    load_exclusions,
    resolve_root_path,
)
from failure_memory.candidate_selector import (  # noqa: E402
    CandidateFeatures,
    FailureFeatures,
    RuleSet,
    extract_candidate_features,
    extract_failure_features,
    rerank_candidates,
    score_payload,
)
from failure_memory.retrieval import FailureQuery, SourceBlindTfidfRetriever  # noqa: E402
from candidate_audit import load_development_config, stable_split_key  # noqa: E402
from benchmark_instances import policy_signature  # noqa: E402
from toolmisusebench.dataset import load_tasks  # noqa: E402


RULES = ROOT / "configs" / "candidate_rules.yaml"
RULE_LOCK = ROOT / "configs" / "candidate_rules.lock.json"
DEFAULT_OUTPUT = ROOT / "outputs" / "candidate_selection" / "selection_manifest.json"


def verify_rule_lock() -> dict[str, Any]:
    lock = json.loads(RULE_LOCK.read_text(encoding="utf-8"))
    if lock.get("status") != "refactored_runtime_lock_after_completed_candidate_development":
        raise RuntimeError("candidate-development runtime lock has an invalid status")
    for name in ("rule_config", "rule_source"):
        item = lock[name]
        path = ROOT / item["path"]
        if sha256_file(path) != item["sha256"]:
            raise RuntimeError(f"locked PROPER v1 {name} hash mismatch")
    return lock


def failure_payload(features: FailureFeatures) -> dict[str, Any]:
    payload = asdict(features)
    payload["state"] = features.state.value
    return payload


def candidate_payload(candidate: CandidateFeatures) -> dict[str, Any]:
    return {
        "experience_id": candidate.experience_id,
        "original_rank": candidate.original_rank,
        "tfidf_score": candidate.tfidf_score,
        "policy_from_text": candidate.policy.value,
        "repair_targets": list(candidate.repair_targets),
        "source_failure": failure_payload(candidate.source_failure),
    }


def condition_metrics(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "count": len(rows),
        "recovery_validity_count": sum(item["recovery_validity"] for item in rows),
        "task_completion_count": sum(item["task_completion"] for item in rows),
        "safety_violation_count": sum(item["safety_violation"] for item in rows),
        "repeated_invalid_calls_total": sum(
            item["repeated_invalid_calls"] for item in rows
        ),
        "recovery_tool_calls_total": sum(item["recovery_tool_calls"] for item in rows),
    }


def run_development() -> dict[str, Any]:
    lock = verify_rule_lock()
    development = load_development_config()
    confirmatory = load_confirmatory_config()
    rule_payload = yaml.safe_load(RULES.read_text(encoding="utf-8"))
    if rule_payload.get("status") != "frozen_before_offline_selector_evaluation":
        raise RuntimeError("PROPER v1 rules are not frozen")
    rules = RuleSet.from_mapping(rule_payload)

    exclusions, _ = load_exclusions(resolve_root_path(confirmatory["pilot_exclusions"]))
    tasks = load_tasks(SAMPLE, str(confirmatory["dataset"]["split"]))
    sources = build_memory_sources(tasks, confirmatory, exclusions)
    source_ids = {item.source_task_id for item in sources}
    targets, rejected = build_targets(tasks, confirmatory, exclusions, source_ids)
    experiences = [as_experience(item) for item in sources]
    experience_by_id = {item.experience_id: item for item in experiences}
    source_by_id = {f"experience::{item.instance_id}": item for item in sources}
    retriever = SourceBlindTfidfRetriever(experiences)

    source_observations = {
        experience_id: prepare_prefix(source)[1]
        for experience_id, source in source_by_id.items()
    }
    retrieval_cache: dict[str, list[Any]] = {}
    rank1_applicable_ids: set[str] = set()
    conflict_ids: list[str] = []
    for target in targets:
        ranked = retriever.retrieve(
            FailureQuery(target.instance_id, target.query_text, target.provenance),
            top_k=int(development["proper_v1"]["top_k"]),
        )
        retrieval_cache[target.instance_id] = ranked
        rank1_applicable = target.applicability[
            policy_signature(ranked[0].experience.policy)
        ]
        if rank1_applicable:
            rank1_applicable_ids.add(target.instance_id)
        else:
            conflict_ids.append(target.instance_id)

    split = development["development_split"]
    ordered_conflicts = sorted(
        conflict_ids,
        key=lambda value: stable_split_key(str(split["seed"]), value),
    )
    design_count = int(split["rule_design_count"])
    design_ids = set(ordered_conflicts[:design_count])
    validation_ids = set(ordered_conflicts[design_count:])

    records: list[dict[str, Any]] = []
    for target in targets:
        _, visible, prefix_sha256 = prepare_prefix(target)
        target_features = extract_failure_features(visible)
        candidates: list[CandidateFeatures] = []
        for item in retrieval_cache[target.instance_id]:
            experience_id = item.experience.experience_id
            natural_text = experience_by_id[experience_id].natural_text
            candidates.append(
                extract_candidate_features(
                    experience_id=experience_id,
                    natural_text=natural_text,
                    original_rank=item.rank,
                    tfidf_score=round(item.score, 12),
                    source_observation=source_observations[experience_id],
                )
            )
        reranked = rerank_candidates(target=target_features, candidates=candidates, rules=rules)
        selected = reranked[0]
        baseline = candidates[0]
        selected_experience = experience_by_id[selected.candidate.experience_id]
        selected_applicable = target.applicability[
            policy_signature(selected_experience.policy)
        ]
        baseline_applicable = target.applicability[
            policy_signature(experience_by_id[baseline.experience_id].policy)
        ]
        if target.instance_id in design_ids:
            partition = "conflict_rule_design"
        elif target.instance_id in validation_ids:
            partition = "conflict_sealed_validation"
        else:
            partition = "rank1_applicable_offline"
        prompt = build_prompt(visible, selected_experience.natural_text)
        records.append(
            {
                "instance_id": target.instance_id,
                "source_task_id": target.source_task_id,
                "development_partition": partition,
                "prefix_sha256": prefix_sha256,
                "target_features": failure_payload(target_features),
                "baseline_rank1_experience_id": baseline.experience_id,
                "proper_selected_experience_id": selected.candidate.experience_id,
                "proper_selected_original_rank": selected.candidate.original_rank,
                "selection_changed": selected.candidate.experience_id != baseline.experience_id,
                "prompt": prompt,
                "prompt_sha256": sha256_text(prompt),
                "evaluator_only": {
                    "baseline_environment_applicable": baseline_applicable,
                    "selected_environment_applicable": selected_applicable,
                },
                "proper_top10": [
                    {
                        "proper_rank": item.proper_rank,
                        "candidate": candidate_payload(item.candidate),
                        "score": score_payload(item.score),
                        "evaluator_only_environment_applicable": target.applicability[
                            policy_signature(
                                experience_by_id[item.candidate.experience_id].policy
                            )
                        ],
                    }
                    for item in reranked
                ],
            }
        )

    rank1_applicable_records = [
        item for item in records if item["instance_id"] in rank1_applicable_ids
    ]
    conflict_records = [item for item in records if item["instance_id"] in set(conflict_ids)]
    exact_preserved = sum(not item["selection_changed"] for item in rank1_applicable_records)
    applicability_preserved = sum(
        item["evaluator_only"]["selected_environment_applicable"]
        for item in rank1_applicable_records
    )
    selected_applicable_conflicts = sum(
        item["evaluator_only"]["selected_environment_applicable"]
        for item in conflict_records
    )
    preservation_rate = exact_preserved / len(rank1_applicable_records)
    threshold = float(
        development["development_go_no_go"][
            "rank1_applicable_offline_preservation_rate_at_least"
        ]
    )

    formal_path = resolve_root_path(development["inputs"]["conditional_results"])
    formal = json.loads(formal_path.read_text(encoding="utf-8"))
    formal_design = {
        item["instance_id"]: item
        for item in formal["records"]
        if item["instance_id"] in design_ids
    }
    selection_by_id = {item["instance_id"]: item for item in records}
    scorable = []
    missing = []
    for instance_id in sorted(design_ids):
        selected_id = selection_by_id[instance_id]["proper_selected_experience_id"]
        row = formal_design[instance_id]
        if selected_id == row["inapplicable_experience_id"]:
            condition = "inapplicable_memory"
        elif selected_id == row["matched_applicable_experience_id"]:
            condition = "matched_applicable_memory"
        else:
            missing.append(
                {
                    "instance_id": instance_id,
                    "proper_selected_experience_id": selected_id,
                    "prompt_sha256": selection_by_id[instance_id]["prompt_sha256"],
                }
            )
            continue
        baseline_outcome = row["conditions"]["inapplicable_memory"]["outcome"]
        proper_outcome = row["conditions"][condition]["outcome"]
        scorable.append(
            {
                "instance_id": instance_id,
                "reused_condition": condition,
                "baseline_outcome": baseline_outcome,
                "proper_outcome": proper_outcome,
                "improvement": (
                    proper_outcome["recovery_validity"]
                    and not baseline_outcome["recovery_validity"]
                ),
                "deterioration": (
                    baseline_outcome["recovery_validity"]
                    and not proper_outcome["recovery_validity"]
                ),
            }
        )

    baseline_outcomes = [item["baseline_outcome"] for item in scorable]
    proper_outcomes = [item["proper_outcome"] for item in scorable]
    design_reuse = {
        "rule_design_count": len(design_ids),
        "existing_output_scorable_count": len(scorable),
        "targeted_output_missing_count": len(missing),
        "baseline": condition_metrics(baseline_outcomes),
        "proper": condition_metrics(proper_outcomes),
        "paired_improvement_count": sum(item["improvement"] for item in scorable),
        "paired_deterioration_count": sum(item["deterioration"] for item in scorable),
        "scorable_case_results": scorable,
        "missing_targeted_prompts": missing,
        "sealed_validation_outcomes_used": False,
    }

    selected_policy_counts = Counter(
        experience_by_id[item["proper_selected_experience_id"]].policy.kind.value
        for item in records
    )
    selected_tool_counts = Counter(
        source_by_id[item["proper_selected_experience_id"]].failure_action.tool_name
        for item in records
    )
    offline = {
        "target_count": len(records),
        "rank1_applicable_count": len(rank1_applicable_records),
        "conflict_count": len(conflict_records),
        "selection_changed_count": sum(item["selection_changed"] for item in records),
        "rank1_applicable_exact_selection_preserved_count": exact_preserved,
        "rank1_applicable_exact_selection_preservation_rate": preservation_rate,
        "rank1_applicable_selected_applicability_preserved_count": applicability_preserved,
        "rank1_applicable_selected_applicability_preservation_rate": (
            applicability_preserved / len(rank1_applicable_records)
        ),
        "conflict_selected_applicable_count": selected_applicable_conflicts,
        "conflict_selected_applicable_rate": (
            selected_applicable_conflicts / len(conflict_records)
        ),
        "selected_policy_counts_evaluator_only": dict(sorted(selected_policy_counts.items())),
        "selected_source_tool_counts": dict(sorted(selected_tool_counts.items())),
        "offline_preservation_gate_threshold": threshold,
        "offline_preservation_gate_pass": preservation_rate >= threshold,
    }
    report = {
        "schema_version": 1,
        "run_kind": "proper_v1_offline_development_selection",
        "identities": {
            "development_config_sha256": sha256_file(
                ROOT / "configs" / "candidate_development.yaml"
            ),
            "rule_lock_sha256": sha256_file(RULE_LOCK),
            "rule_config_sha256": lock["rule_config"]["sha256"],
            "rule_source_sha256": lock["rule_source"]["sha256"],
            "conditional_results_sha256": sha256_file(formal_path),
        },
        "boundary": {
            "new_model_output_generated": False,
            "sealed_validation_outcomes_used": False,
            "development_only_not_confirmatory": True,
        },
        "offline_selection": offline,
        "rule_design_existing_output_reuse": design_reuse,
        "target_rejected_counts": rejected,
        "records": records,
    }
    report["identities"]["selection_payload_sha256"] = sha256_text(
        json.dumps(report, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run frozen PROPER v1 offline development.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_development()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {key: value for key, value in report.items() if key != "records"}
    print(json.dumps(summary, indent=2, sort_keys=True))
    if report["offline_selection"]["offline_preservation_gate_pass"]:
        result = "PASS_PROPER_V1_OFFLINE_DEVELOPMENT"
    else:
        result = "STOP_PROPER_V1_OFFLINE_PRESERVATION_GATE"
    print(f"RESULT={result}")
    print("NOTE=No model was loaded and sealed validation outcomes were not used.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
