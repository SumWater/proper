from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "extension_capacity_audit.yaml"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def provenance(record: Mapping[str, Any]) -> str:
    parts = str(record["instance_id"]).split("::", 1)
    if len(parts) != 2 or not parts[1]:
        raise ValueError("instance_id must contain a provenance suffix")
    return parts[1]


def ordered_candidates(record: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    values = sorted(
        record["proper_top10"], key=lambda item: int(item["candidate"]["original_rank"])
    )
    ranks = [int(item["candidate"]["original_rank"]) for item in values]
    if not ranks or ranks[0] != 1 or ranks != list(range(1, len(values) + 1)):
        raise ValueError("candidate ranks must be complete and start at one")
    return values


def applicable(candidate: Mapping[str, Any]) -> bool:
    return bool(candidate["evaluator_only_environment_applicable"])


def best_replacement(
    record: Mapping[str, Any], depth: int
) -> Mapping[str, Any] | None:
    candidates = ordered_candidates(record)
    if applicable(candidates[0]):
        return None
    return next(
        (
            item
            for item in candidates
            if int(item["candidate"]["original_rank"]) <= depth and applicable(item)
        ),
        None,
    )


def structural_signature(record: Mapping[str, Any]) -> dict[str, Any]:
    """Agent-visible normalized structure; no IDs, provenance, or evaluator labels."""

    features = record["target_features"]
    return {
        "state": features["state"],
        "error_code": features["error_code"],
        "tool_name": features["tool_name"],
        "missing_fields": list(features["missing_fields"]),
        "public_schema_fields": list(features["public_schema_fields"]),
        "public_required_fields": list(features["public_required_fields"]),
        "schema_signature": features["schema_signature"],
        "failed_argument_paths": list(features["failed_argument_paths"]),
        "repeated_same_call_count": int(features["repeated_same_call_count"]),
    }


def depth_counts(records: Iterable[Mapping[str, Any]], depth: int) -> dict[str, int]:
    values = list(records)
    available = 0
    conflicts = 0
    for record in values:
        candidates = ordered_candidates(record)
        within_depth = [
            item
            for item in candidates
            if int(item["candidate"]["original_rank"]) <= depth
        ]
        available += int(any(applicable(item) for item in within_depth))
        conflicts += int(not applicable(candidates[0]) and any(applicable(item) for item in within_depth))
    return {
        "applicable_candidate_available_count": available,
        "rank1_inapplicable_with_replacement_count": conflicts,
    }


def replacement_diversity(records: Iterable[Mapping[str, Any]], depth: int) -> dict[str, Any]:
    replacements = [best_replacement(record, depth) for record in records]
    replacements = [item for item in replacements if item is not None]
    experience_counts = Counter(
        str(item["candidate"]["experience_id"]) for item in replacements
    )
    source_tools = Counter(
        str(item["candidate"]["source_failure"]["tool_name"]) for item in replacements
    )
    policies = Counter(str(item["candidate"]["policy_from_text"]) for item in replacements)
    maximum = max(experience_counts.values(), default=0)
    return {
        "replacement_count": len(replacements),
        "distinct_experience_count": len(experience_counts),
        "distinct_source_tool_count": len(source_tools),
        "distinct_policy_count": len(policies),
        "policy_counts": dict(sorted(policies.items())),
        "source_tool_counts": dict(sorted(source_tools.items())),
        "maximum_single_experience_count": maximum,
        "maximum_single_experience_share": maximum / len(replacements) if replacements else 0.0,
    }


def family_summary(
    records: list[Mapping[str, Any]], depths: list[int], thresholds: Mapping[str, Any]
) -> dict[str, Any]:
    candidates = [ordered_candidates(record) for record in records]
    baseline_applicable = sum(applicable(items[0]) for items in candidates)
    tools = sorted({str(record["target_features"]["tool_name"]) for record in records})
    by_depth = {str(depth): depth_counts(records, depth) for depth in depths}
    diversity = replacement_diversity(records, max(depths))
    top_depth = by_depth[str(max(depths))]
    checks = {
        "target_capacity_met": len(records)
        >= int(thresholds["minimum_targets_per_family"]),
        "tool_diversity_met": len(tools)
        >= int(thresholds["minimum_distinct_tools_per_family"]),
        "intervention_capacity_met": top_depth[
            "rank1_inapplicable_with_replacement_count"
        ]
        >= int(thresholds["minimum_rank1_conflicts_with_top10_replacement"]),
        "replacement_memory_diversity_met": diversity["distinct_experience_count"]
        >= int(thresholds["minimum_distinct_top10_replacement_memories"]),
    }
    return {
        "target_count": len(records),
        "provenance_counts": dict(sorted(Counter(provenance(item) for item in records).items())),
        "rank1_applicable_count": baseline_applicable,
        "rank1_inapplicable_count": len(records) - baseline_applicable,
        "distinct_target_tool_count": len(tools),
        "target_tools": tools,
        "candidate_depths": by_depth,
        "top10_replacement_diversity": diversity,
        "readiness_checks": checks,
        "all_readiness_checks_met": all(checks.values()),
    }


def alias_summary(
    records: list[Mapping[str, Any]], left: set[str], right: set[str]
) -> dict[str, Any]:
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        if provenance(record) in left | right:
            groups[canonical(structural_signature(record))].append(record)
    shared = [
        members
        for members in groups.values()
        if {provenance(item) for item in members} & left
        and {provenance(item) for item in members} & right
    ]
    return {
        "shared_signature_group_count": len(shared),
        "left_target_count_in_shared_groups": sum(
            provenance(item) in left for members in shared for item in members
        ),
        "right_target_count_in_shared_groups": sum(
            provenance(item) in right for members in shared for item in members
        ),
        "current_structural_prefix_is_fully_identifying": not shared,
    }


def run_audit(config_path: Path = CONFIG) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    manifest_path = ROOT / config["input"]["selection_manifest"]
    actual_manifest_sha = sha256_file(manifest_path)
    if actual_manifest_sha != str(config["input"]["selection_manifest_sha256"]):
        raise RuntimeError("frozen selection manifest hash mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = manifest["records"]
    if len(records) != int(config["input"]["expected_target_count"]):
        raise RuntimeError("unexpected development target count")

    configured_provenances = {
        value
        for family in config["families"].values()
        for value in family["provenances"]
    }
    observed_provenances = {provenance(record) for record in records}
    if configured_provenances != observed_provenances:
        raise RuntimeError("family mapping does not cover the development population exactly")

    depths = [int(value) for value in config["candidate_depths"]]
    family_results = {}
    for name, definition in config["families"].items():
        accepted = set(definition["provenances"])
        members = [record for record in records if provenance(record) in accepted]
        family_results[name] = family_summary(
            members, depths, config["development_readiness"]
        )

    alias_results = {}
    for check in config["observable_alias_checks"]:
        result = alias_summary(
            records,
            set(check["left_provenances"]),
            set(check["right_provenances"]),
        )
        result["conflicting_recovery_policies"] = list(
            check["conflicting_recovery_policies"]
        )
        alias_results[str(check["name"])] = result

    authorization_strata = {}
    for name, accepted in {
        "transient_native": {"authorization_transient"},
        "persistent_local_extension": {"authorization_persistent_extension"},
    }.items():
        members = [record for record in records if provenance(record) in accepted]
        authorization_strata[name] = family_summary(
            members, depths, config["development_readiness"]
        )

    native = ["schema_drift", "timeout", "authorization"]
    return {
        "schema_version": 1,
        "run_kind": "exploratory_proper_v2_extension_capacity_audit",
        "identities": {
            "config_sha256": sha256_file(config_path),
            "selection_manifest_sha256": actual_manifest_sha,
        },
        "boundary": {
            "development_data_only": True,
            "model_loaded": False,
            "model_outputs_read": False,
            "evaluator_applicability_used_only_for_capacity_counts": True,
            "hidden_labels_used_by_future_agent": False,
            "gate_refit_performed": False,
            "gpu_run_authorized": False,
        },
        "population": {
            "target_count": len(records),
            "candidate_depths": depths,
            "family_count": len(family_results),
        },
        "families": family_results,
        "authorization_strata": authorization_strata,
        "observable_aliasing": alias_results,
        "safety_feasibility": {
            "persistent_authorization_retry_is_safety_violation": bool(
                config["safety_constraints"][
                    "persistent_authorization_retry_is_safety_violation"
                ]
            ),
            "safety_violation_invalidates_recovery_validity": bool(
                config["safety_constraints"][
                    "safety_violation_invalidates_recovery_validity"
                ]
            ),
            "repeated_denial_requires_prior_retry": bool(
                config["safety_constraints"]["repeated_denial_requires_prior_retry"]
            ),
            "safe_stateful_authorization_probe_available": False,
        },
        "planning_decision": {
            "native_families_all_capacity_ready": all(
                family_results[name]["all_readiness_checks_met"] for name in native
            ),
            "direct_one_step_generalization_ready": all(
                item["current_structural_prefix_is_fully_identifying"]
                for item in alias_results.values()
            ),
            "unsafe_diagnostic_retry_rejected": True,
            "next_action": "audit_native_transient_authorization_public_test_capacity",
        },
        "interpretation_limits": {
            "capacity_is_not_recovery_validity_evidence": True,
            "development_labels_are_not_confirmatory_evidence": True,
            "no_new_model_result_was_generated": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit cross-failure PROPER v2 capacity.")
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    output = args.output or ROOT / config["output"]["path"]
    payload = run_audit(args.config)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "families": payload["families"],
                "authorization_strata": payload["authorization_strata"],
                "observable_aliasing": payload["observable_aliasing"],
                "safety_feasibility": payload["safety_feasibility"],
                "planning_decision": payload["planning_decision"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    print("RESULT=COMPLETE_PROPER_V2_EXTENSION_CAPACITY_AUDIT")
    print("NOTE=No model was loaded and no model output was read or generated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
