from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "external" / "toolmisusebench"))

from agent_runtime import (  # noqa: E402
    canonical,
    prepare_prefix,
    sha256_file,
    sha256_text,
)
from gate_dataset import (  # noqa: E402
    SAMPLE,
    as_experience,
    build_memory_sources,
    build_targets,
    load_config as load_confirmatory_config,
    load_exclusions,
    resolve_root_path,
)
from failure_memory.retrieval import FailureQuery, SourceBlindTfidfRetriever  # noqa: E402
from benchmark_instances import experience_text, policy_signature  # noqa: E402
from toolmisusebench.dataset import load_tasks  # noqa: E402


CONFIG = ROOT / "configs" / "proper_v1" / "candidate_development.yaml"
DEFAULT_OUTPUT = ROOT / "outputs" / "proper_v1" / "candidate_selection" / "development_audit.json"


def load_development_config(path: Path = CONFIG) -> dict[str, Any]:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if config.get("status") != "refactored_runtime_after_completed_candidate_development":
        raise RuntimeError("candidate-development runtime configuration has an invalid status")
    return config


def stable_split_key(seed: str, instance_id: str) -> str:
    return hashlib.sha256(f"{seed}:{instance_id}".encode("utf-8")).hexdigest()


def flatten_paths(value: Any, prefix: str = "") -> tuple[str, ...]:
    if not isinstance(value, Mapping):
        return (prefix or "/",)
    paths: list[str] = []
    for key in sorted(value, key=str):
        child = f"{prefix}/{key}"
        if isinstance(value[key], Mapping) and value[key]:
            paths.extend(flatten_paths(value[key], child))
        else:
            paths.append(child)
    return tuple(paths)


def relevant_schema(visible: dict[str, Any], tool_name: str) -> dict[str, Any] | None:
    return next(
        (item for item in visible.get("tool_schemas", []) if item.get("name") == tool_name),
        None,
    )


def observable_failure_evidence(instance: Any) -> dict[str, Any]:
    _, visible, prefix_sha256 = prepare_prefix(instance)
    transcript = visible.get("transcript", [])
    failed = transcript[-1] if transcript else {}
    error = visible.get("last_error") or {}
    details = error.get("details") or {}
    tool_name = str(failed.get("tool_name") or instance.failure_action.tool_name)
    repeated_same_call_count = sum(
        item.get("tool_name") == tool_name
        and canonical(item.get("args", {})) == canonical(failed.get("args", {}))
        for item in transcript
    )
    schema = relevant_schema(visible, tool_name)
    return {
        "instruction": visible.get("instruction"),
        "failed_tool_name": tool_name,
        "failed_argument_paths": list(flatten_paths(failed.get("args", {}))),
        "error_code": error.get("code"),
        "error_message": error.get("message"),
        "error_detail_keys": sorted(str(key) for key in details),
        "missing_fields": sorted(str(value) for value in details.get("missing", [])),
        "schema": schema,
        "repeated_same_call_count": repeated_same_call_count,
        "remaining_budget": visible.get("remaining_budget"),
        "prefix_sha256": prefix_sha256,
    }


def observable_candidate_policy(natural_text: str) -> str:
    if "retried the original tool call once" in natural_text:
        return "retry_original_call_once"
    if "corrected the missing arguments" in natural_text:
        return "repair_missing_arguments"
    if "stopped without another tool call" in natural_text:
        return "stop_and_report"
    return "unparsed"


def pair_table(
    rows: Iterable[dict[str, Any]], left: Any, right: Any
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        counts[f"{left(row)} -> {right(row)}"] += 1
    return dict(sorted(counts.items()))


def condition_outcome(row: dict[str, Any], condition: str) -> dict[str, Any]:
    return row["conditions"][condition]["outcome"]


def audit(config_path: Path = CONFIG) -> dict[str, Any]:
    development = load_development_config(config_path)
    confirmatory = load_confirmatory_config()
    exclusions, _ = load_exclusions(resolve_root_path(confirmatory["pilot_exclusions"]))
    tasks = load_tasks(SAMPLE, str(confirmatory["dataset"]["split"]))
    sources = build_memory_sources(tasks, confirmatory, exclusions)
    source_ids = {item.source_task_id for item in sources}
    targets, rejected = build_targets(tasks, confirmatory, exclusions, source_ids)
    experiences = [as_experience(item) for item in sources]
    source_by_experience = {
        f"experience::{item.instance_id}": item for item in sources
    }
    retriever = SourceBlindTfidfRetriever(experiences)

    result_path = resolve_root_path(development["inputs"]["conditional_results"])
    formal = json.loads(result_path.read_text(encoding="utf-8"))
    result_by_id = {item["instance_id"]: item for item in formal["records"]}
    conflict_ids = sorted(result_by_id)
    split = development["development_split"]
    ordered_conflicts = sorted(
        conflict_ids,
        key=lambda value: stable_split_key(str(split["seed"]), value),
    )
    design_count = int(split["rule_design_count"])
    design_ids = set(ordered_conflicts[:design_count])
    validation_ids = set(ordered_conflicts[design_count:])
    if len(design_ids) != design_count or len(validation_ids) != int(
        split["sealed_validation_count"]
    ):
        raise RuntimeError("frozen development split counts do not match the formal output")

    records: list[dict[str, Any]] = []
    matched_ranks: dict[str, int] = {}
    reconstructed_prompt_count = 0
    fixed_bank_hash = sha256_text(
        canonical(
            [
                {
                    "experience_id": item.experience_id,
                    "natural_text": item.natural_text,
                    "source_instance_id": item.source_instance_id,
                }
                for item in experiences
            ]
        )
    )
    for target in targets:
        ranked = retriever.retrieve(
            FailureQuery(target.instance_id, target.query_text, target.provenance),
            top_k=len(experiences),
        )
        first_applicable = next(
            (
                item
                for item in ranked
                if target.applicability[policy_signature(item.experience.policy)]
            ),
            None,
        )
        if first_applicable is None:
            matched_rank = None
            matched_id = None
        else:
            matched_rank = first_applicable.rank
            matched_id = first_applicable.experience.experience_id
            matched_ranks[target.instance_id] = matched_rank

        rank1_applicable = target.applicability[
            policy_signature(ranked[0].experience.policy)
        ]
        if target.instance_id in design_ids:
            partition = "conflict_rule_design"
        elif target.instance_id in validation_ids:
            partition = "conflict_sealed_validation"
        else:
            partition = "rank1_applicable_offline"
        target_evidence = observable_failure_evidence(target)
        candidates = []
        for item in ranked[: int(development["proper_v1"]["top_k"])]:
            source = source_by_experience[item.experience.experience_id]
            source_evidence = observable_failure_evidence(source)
            candidates.append(
                {
                    "rank": item.rank,
                    "experience_id": item.experience.experience_id,
                    "source_instance_id": item.experience.source_instance_id,
                    "source_task_id": source.source_task_id,
                    "tfidf_score": round(item.score, 12),
                    "natural_text": item.experience.natural_text,
                    "observable": {
                        "source_tool_name": source.failure_action.tool_name,
                        "source_error_code": source_evidence["error_code"],
                        "source_error_detail_keys": source_evidence["error_detail_keys"],
                        "source_missing_fields": source_evidence["missing_fields"],
                        "recovery_policy_from_text": observable_candidate_policy(
                            item.experience.natural_text
                        ),
                    },
                    "evaluator_only": {
                        "source_provenance": source.provenance,
                        "structured_recovery_policy": {
                            "kind": item.experience.policy.kind.value,
                            "parameters": dict(item.experience.policy.parameters),
                        },
                        "environment_applicable": target.applicability[
                            policy_signature(item.experience.policy)
                        ],
                    },
                }
            )
        records.append(
            {
                "instance_id": target.instance_id,
                "source_task_id": target.source_task_id,
                "development_partition": partition,
                "observable_target": target_evidence,
                "retrieval": {
                    "rank1_applicable_evaluator_only": rank1_applicable,
                    "first_applicable_rank_evaluator_only": matched_rank,
                    "first_applicable_experience_id_evaluator_only": matched_id,
                    "candidates_top10": candidates,
                },
            }
        )

        if target.instance_id in result_by_id:
            formal_row = result_by_id[target.instance_id]
            if matched_id != formal_row["matched_applicable_experience_id"]:
                raise RuntimeError(
                    f"matched-applicable reconstruction mismatch: {target.instance_id}"
                )
            selected_id = formal_row["inapplicable_experience_id"]
            selected = source_by_experience[selected_id]
            matched = source_by_experience[matched_id]
            _, visible, _ = prepare_prefix(target)
            from agent_runtime import build_prompt  # local import keeps audit boundary explicit

            expected_prompts = {
                "inapplicable_memory": build_prompt(visible, experience_text(selected)),
                "matched_applicable_memory": build_prompt(visible, experience_text(matched)),
            }
            for condition, expected in expected_prompts.items():
                if formal_row["conditions"][condition]["prompt"] != expected:
                    raise RuntimeError(
                        f"formal prompt contains a non-reconstructed memory: "
                        f"{target.instance_id} {condition}"
                    )
                reconstructed_prompt_count += 1

    conflict_rows = [result_by_id[value] for value in conflict_ids]
    design_rows = [result_by_id[value] for value in ordered_conflicts[:design_count]]

    oracle_by_depth: dict[str, Any] = {}
    for depth in development["retrieval_audit"]["candidate_depths"] + [20, 100]:
        eligible_rows = [row for row in conflict_rows if matched_ranks[row["instance_id"]] <= depth]
        rank1_valid = [
            condition_outcome(row, "inapplicable_memory")["recovery_validity"]
            for row in eligible_rows
        ]
        oracle_valid = [
            condition_outcome(row, "matched_applicable_memory")["recovery_validity"]
            for row in eligible_rows
        ]
        oracle_by_depth[str(depth)] = {
            "candidate_available_count": len(eligible_rows),
            "rank1_recovery_validity_count": sum(rank1_valid),
            "applicability_oracle_recovery_validity_count": sum(oracle_valid),
            "paired_improvement_count": sum(
                current and not baseline
                for baseline, current in zip(rank1_valid, oracle_valid, strict=True)
            ),
            "paired_deterioration_count": sum(
                baseline and not current
                for baseline, current in zip(rank1_valid, oracle_valid, strict=True)
            ),
            "net_paired_effect": (
                (sum(oracle_valid) - sum(rank1_valid)) / len(eligible_rows)
                if eligible_rows
                else None
            ),
        }

    design_improvements = []
    for row in design_rows:
        rank1 = condition_outcome(row, "inapplicable_memory")["recovery_validity"]
        oracle = condition_outcome(row, "matched_applicable_memory")["recovery_validity"]
        if oracle and not rank1:
            design_improvements.append(
                {
                    "instance_id": row["instance_id"],
                    "source_task_id": row["source_task_id"],
                    "target_tool": row["failed_action"]["tool_name"],
                    "rank1_policy": row["inapplicable_policy"]["kind"],
                    "oracle_policy": row["matched_applicable_policy"]["kind"],
                    "oracle_rank": matched_ranks[row["instance_id"]],
                }
            )

    rv_transition = lambda row: (  # noqa: E731
        condition_outcome(row, "no_memory")["recovery_validity"],
        condition_outcome(row, "inapplicable_memory")["recovery_validity"],
    )
    crosstabs = {
        "recovery_validity_no_memory_to_rank1": pair_table(
            conflict_rows, lambda row: rv_transition(row)[0], lambda row: rv_transition(row)[1]
        ),
        "safety_violation_no_memory_to_rank1": pair_table(
            conflict_rows,
            lambda row: condition_outcome(row, "no_memory")["safety_violation"],
            lambda row: condition_outcome(row, "inapplicable_memory")["safety_violation"],
        ),
        "repeated_invalid_calls_no_memory_to_rank1": pair_table(
            conflict_rows,
            lambda row: condition_outcome(row, "no_memory")["repeated_invalid_calls"],
            lambda row: condition_outcome(row, "inapplicable_memory")[
                "repeated_invalid_calls"
            ],
        ),
        "miac_by_recovery_validity_transition": pair_table(
            conflict_rows,
            lambda row: row["primary_pair_indicators"]["memory_induced_action_change"],
            lambda row: f"{rv_transition(row)[0]}->{rv_transition(row)[1]}",
        ),
        "strict_adoption_by_recovery_validity_transition": pair_table(
            conflict_rows,
            lambda row: row["primary_pair_indicators"]["strict_policy_adoption"],
            lambda row: f"{rv_transition(row)[0]}->{rv_transition(row)[1]}",
        ),
        "miac_by_strict_adoption": pair_table(
            conflict_rows,
            lambda row: row["primary_pair_indicators"]["memory_induced_action_change"],
            lambda row: row["primary_pair_indicators"]["strict_policy_adoption"],
        ),
    }

    availability = {}
    for population_name, population in {
        "all_332_targets": records,
        "rank1_inapplicable_104_conflicts": [
            item for item in records if item["instance_id"] in result_by_id
        ],
    }.items():
        count = len(population)
        availability[population_name] = {
            f"applicable_recall_at_{depth}": sum(
                item["retrieval"]["first_applicable_rank_evaluator_only"] <= depth
                for item in population
            )
            / count
            for depth in development["retrieval_audit"]["candidate_depths"]
        }
        availability[population_name]["count"] = count

    design_concentration = {
        "improvement_count": len(design_improvements),
        "by_target_tool": dict(sorted(Counter(
            item["target_tool"] for item in design_improvements
        ).items())),
        "by_rank1_policy": dict(sorted(Counter(
            item["rank1_policy"] for item in design_improvements
        ).items())),
        "by_oracle_policy": dict(sorted(Counter(
            item["oracle_policy"] for item in design_improvements
        ).items())),
        "case_list": design_improvements,
        "sealed_validation_case_outcomes_included": False,
    }

    return {
        "schema_version": 1,
        "run_kind": "proper_v1_development_audit",
        "identities": {
            "development_config_sha256": sha256_file(config_path),
            "confirmatory_config_sha256": sha256_file(
                resolve_root_path(development["inputs"]["confirmatory_config"])
            ),
            "prepared_cohort_sha256": sha256_file(
                resolve_root_path(development["inputs"]["prepared_cohort"])
            ),
            "conditional_results_sha256": sha256_file(result_path),
            "fixed_memory_bank_sha256": fixed_bank_hash,
        },
        "audit_boundary": {
            "purpose": development["purpose"],
            "validation_case_level_outcomes_sealed": True,
            "new_model_output_generated": False,
        },
        "memory_bank_audit": {
            "fixed_memory_bank_count": len(experiences),
            "same_bank_used_for_every_target": True,
            "matched_applicable_selection_depth": len(experiences),
            "matched_applicable_is_top10_for_all_104": all(
                value <= 10 for value in matched_ranks.values()
            ),
            "matched_applicable_prompt_reconstructed_without_rewrite_count": (
                reconstructed_prompt_count // 2
            ),
            "matched_rank_counts": dict(sorted(Counter(matched_ranks.values()).items())),
        },
        "development_split": {
            "seed": split["seed"],
            "rule_design_count": len(design_ids),
            "sealed_validation_count": len(validation_ids),
            "rule_design_ids": sorted(design_ids),
            "sealed_validation_ids_sha256": sha256_text(canonical(sorted(validation_ids))),
        },
        "candidate_availability": availability,
        "applicability_oracle_online_audit": oracle_by_depth,
        "rule_design_improvement_concentration": design_concentration,
        "paired_crosstabs_all_104_existing_results": crosstabs,
        "target_rejected_counts": rejected,
        "records": records,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit PROPER v1 Top-10 development data.")
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = audit(args.config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {key: value for key, value in report.items() if key != "records"}
    print(json.dumps(summary, indent=2, sort_keys=True))
    print("RESULT=PASS_PROPER_V1_DEVELOPMENT_AUDIT")
    print("NOTE=No model was loaded and sealed validation case outcomes were not exposed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
