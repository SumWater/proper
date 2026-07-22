from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "observable_identifiability_audit.yaml"
DEFAULT_OUTPUT = ROOT / "outputs" / "observable_identifiability" / "audit.json"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def baseline_candidate(record: Mapping[str, Any]) -> Mapping[str, Any]:
    values = [
        item
        for item in record["proper_top10"]
        if int(item["candidate"]["original_rank"]) == 1
    ]
    if len(values) != 1:
        raise ValueError("record must contain exactly one original Rank-1 candidate")
    return values[0]


def intervention_label(record: Mapping[str, Any]) -> bool:
    """Evaluator-only label joined after signature construction."""

    baseline = baseline_candidate(record)
    baseline_applicable = bool(baseline["evaluator_only_environment_applicable"])
    replacement_available = any(
        bool(item["evaluator_only_environment_applicable"])
        for item in record["proper_top10"]
    )
    return not baseline_applicable and replacement_available


def observable_signature(record: Mapping[str, Any], level: str) -> dict[str, Any]:
    features = record["target_features"]
    ordered_candidates = sorted(
        record["proper_top10"], key=lambda item: int(item["candidate"]["original_rank"])
    )
    baseline_policy = str(ordered_candidates[0]["candidate"]["policy_from_text"])
    if level == "state_and_baseline_policy":
        return {
            "failure_state": features["state"],
            "baseline_policy_from_text": baseline_policy,
        }
    if level == "state_tool_and_baseline_policy":
        return {
            "failure_state": features["state"],
            "tool_name": features["tool_name"],
            "baseline_policy_from_text": baseline_policy,
        }
    structural_levels = {
        "normalized_structural_and_baseline_policy",
        "normalized_structural_with_candidate_policy_counts",
        "normalized_structural_with_candidate_profiles",
    }
    if level not in structural_levels:
        raise ValueError(f"unknown signature level: {level}")
    signature = {
        "failure_state": features["state"],
        "error_code": features["error_code"],
        "tool_name": features["tool_name"],
        "missing_fields": list(features["missing_fields"]),
        "public_schema_fields": list(features["public_schema_fields"]),
        "public_required_fields": list(features["public_required_fields"]),
        "schema_signature": features["schema_signature"],
        "failed_argument_paths": list(features["failed_argument_paths"]),
        "repeated_same_call_count": features["repeated_same_call_count"],
        "baseline_policy_from_text": baseline_policy,
    }
    if level == "normalized_structural_with_candidate_policy_counts":
        signature["candidate_policy_counts"] = dict(
            sorted(
                Counter(
                    str(item["candidate"]["policy_from_text"])
                    for item in ordered_candidates
                ).items()
            )
        )
    elif level == "normalized_structural_with_candidate_profiles":
        signature["candidate_profiles"] = [
            {
                "original_rank": int(item["candidate"]["original_rank"]),
                "policy_from_text": str(item["candidate"]["policy_from_text"]),
                "source_failure_state": str(
                    item["candidate"]["source_failure"]["state"]
                ),
                "source_tool_name": str(
                    item["candidate"]["source_failure"]["tool_name"]
                ),
                "repair_targets": list(item["candidate"]["repair_targets"]),
            }
            for item in ordered_candidates
        ]
    return signature


def summarize_level(records: list[Mapping[str, Any]], level: str) -> dict[str, Any]:
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    signatures: dict[str, dict[str, Any]] = {}
    for record in records:
        signature = observable_signature(record, level)
        key = canonical(signature)
        signatures[key] = signature
        groups[key].append(record)

    ambiguous = []
    majority_correct = 0
    for key, members in sorted(groups.items()):
        positive = sum(intervention_label(record) for record in members)
        negative = len(members) - positive
        majority_correct += max(positive, negative)
        if positive and negative:
            ambiguous.append(
                {
                    "signature": signatures[key],
                    "target_count": len(members),
                    "intervention_available_count": positive,
                    "keep_or_no_replacement_count": negative,
                    "majority_trigger": positive > negative,
                    "majority_correct_count": max(positive, negative),
                    "evaluator_only_provenance_counts": dict(
                        sorted(
                            Counter(
                                str(record["instance_id"]).split("::", 1)[1]
                                for record in members
                            ).items()
                        )
                    ),
                }
            )
    ambiguous.sort(
        key=lambda item: (
            -int(item["target_count"]),
            canonical(item["signature"]),
        )
    )
    return {
        "signature_level": level,
        "signature_group_count": len(groups),
        "ambiguous_group_count": len(ambiguous),
        "ambiguous_target_count": sum(item["target_count"] for item in ambiguous),
        "deterministic_majority_correct_count": majority_correct,
        "deterministic_majority_accuracy": majority_correct / len(records),
        "ambiguous_groups": ambiguous,
    }


def run_audit() -> dict[str, Any]:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    manifest_path = ROOT / config["input"]["selection_manifest"]
    if sha256_file(manifest_path) != config["input"]["selection_manifest_sha256"]:
        raise RuntimeError("frozen selection manifest hash mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = manifest["records"]
    if len(records) != int(config["input"]["target_count"]):
        raise RuntimeError("unexpected target population")

    positives = sum(intervention_label(record) for record in records)
    baseline_applicable = sum(
        bool(baseline_candidate(record)["evaluator_only_environment_applicable"])
        for record in records
    )
    no_top10_replacement = sum(
        not bool(baseline_candidate(record)["evaluator_only_environment_applicable"])
        and not any(
            bool(item["evaluator_only_environment_applicable"])
            for item in record["proper_top10"]
        )
        for record in records
    )
    return {
        "schema_version": 1,
        "run_kind": "exploratory_observable_identifiability_audit",
        "identities": {
            "config_sha256": sha256_file(CONFIG),
            "selection_manifest_sha256": sha256_file(manifest_path),
        },
        "boundary": {
            "model_loaded": False,
            "model_outputs_read": False,
            "validation_model_outcomes_read": False,
            "hidden_fields_used_in_signature": False,
            "evaluator_labels_joined_after_signature_construction": True,
            "exploratory_development_only": True,
        },
        "population": {
            "target_count": len(records),
            "rank1_applicable_count": baseline_applicable,
            "rank1_inapplicable_with_top10_replacement_count": positives,
            "rank1_inapplicable_without_top10_replacement_count": no_top10_replacement,
        },
        "always_keep_baseline": {
            "correct_count": len(records) - positives,
            "accuracy": (len(records) - positives) / len(records),
        },
        "signature_analyses": [
            summarize_level(records, level)
            for level in config["signature_levels"]
        ],
        "interpretation_limits": {
            "majority_accuracy_is_not_model_recovery_validity": True,
            "does_not_prove_impossibility_for_all_observable_models": True,
            "does_not_authorize_post_hoc_selector_tuning": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    payload = run_audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary = {
        "population": payload["population"],
        "always_keep_baseline": payload["always_keep_baseline"],
        "signature_analyses": [
            {key: value for key, value in item.items() if key != "ambiguous_groups"}
            for item in payload["signature_analyses"]
        ],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    print("RESULT=COMPLETE_EXPLORATORY_IDENTIFIABILITY_AUDIT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
