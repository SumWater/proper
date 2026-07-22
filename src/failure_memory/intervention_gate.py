"""Public-feature extraction for the applicability intervention gate."""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping


def ordered_top10(record: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    values = sorted(
        record["proper_top10"], key=lambda item: int(item["candidate"]["original_rank"])
    )
    ranks = [int(item["candidate"]["original_rank"]) for item in values]
    if ranks != list(range(1, 11)):
        raise ValueError("record must contain original TF-IDF ranks 1 through 10")
    return values


def _set_indicators(
    features: dict[str, Any], prefix: str, values: list[Any] | tuple[Any, ...]
) -> None:
    for value in sorted(str(item) for item in values):
        features[f"{prefix}::{value}"] = 1


def extract_gate_features(record: Mapping[str, Any]) -> dict[str, Any]:
    """Extract only the feature family frozen in the gate protocol."""

    target = record["target_features"]
    candidates = ordered_top10(record)
    features: dict[str, Any] = {
        "target_failure_state": str(target["state"]),
        "target_error_code": str(target["error_code"]),
        "target_tool_name": str(target["tool_name"]),
        "target_repeated_same_call_count": int(target["repeated_same_call_count"]),
        "target_missing_field_count": len(target["missing_fields"]),
        "target_schema_field_count": len(target["public_schema_fields"]),
        "target_required_field_count": len(target["public_required_fields"]),
        "target_failed_argument_path_count": len(target["failed_argument_paths"]),
    }
    _set_indicators(features, "target_missing_field", target["missing_fields"])
    _set_indicators(features, "target_schema_field", target["public_schema_fields"])
    _set_indicators(features, "target_required_field", target["public_required_fields"])
    _set_indicators(features, "target_failed_argument_path", target["failed_argument_paths"])

    policy_counts: Counter[str] = Counter()
    compatibility_counts: Counter[str] = Counter()
    contradiction_free_compatible_count = 0
    target_missing = set(str(value) for value in target["missing_fields"])
    for item in candidates:
        candidate = item["candidate"]
        score = item["score"]
        rank = int(candidate["original_rank"])
        prefix = f"candidate_rank_{rank}"
        policy = str(candidate["policy_from_text"])
        compatibility = str(score["policy_compatibility"])
        source = candidate["source_failure"]
        repair_targets = [str(value) for value in candidate["repair_targets"]]
        contradictions = [str(value) for value in score["contradictions"]]
        policy_counts[policy] += 1
        compatibility_counts[compatibility] += 1
        if compatibility == "compatible" and not contradictions:
            contradiction_free_compatible_count += 1
        features.update(
            {
                f"{prefix}_policy": policy,
                f"{prefix}_source_failure_state": str(source["state"]),
                f"{prefix}_source_tool_name": str(source["tool_name"]),
                f"{prefix}_same_tool": int(
                    str(source["tool_name"]) == str(target["tool_name"])
                ),
                f"{prefix}_repair_target_overlap": len(
                    target_missing & set(repair_targets)
                ),
                f"{prefix}_policy_compatibility": compatibility,
                f"{prefix}_contradiction_count": len(contradictions),
            }
        )
        _set_indicators(features, f"{prefix}_repair_target", repair_targets)

    for policy, count in sorted(policy_counts.items()):
        features[f"candidate_policy_count::{policy}"] = count
    for compatibility, count in sorted(compatibility_counts.items()):
        features[f"candidate_compatibility_count::{compatibility}"] = count
    features["contradiction_free_compatible_count"] = (
        contradiction_free_compatible_count
    )
    return features


def applicability_intervention_label(record: Mapping[str, Any]) -> bool:
    """Compute the evaluator-only development label outside feature extraction."""

    candidates = ordered_top10(record)
    baseline_applicable = bool(
        candidates[0]["evaluator_only_environment_applicable"]
    )
    replacement_available = any(
        bool(item["evaluator_only_environment_applicable"])
        for item in candidates
    )
    return not baseline_applicable and replacement_available


def selected_applicability(record: Mapping[str, Any], experience_id: str) -> bool:
    matches = [
        item
        for item in ordered_top10(record)
        if str(item["candidate"]["experience_id"]) == experience_id
    ]
    if len(matches) != 1:
        raise ValueError("selected experience is not unique in Top-10")
    return bool(matches[0]["evaluator_only_environment_applicable"])
