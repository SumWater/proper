from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

import yaml


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs" / "paper_2026" / "e5_concentration_v1_0.yaml"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def root_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def verify(config: Mapping[str, Any]) -> dict[str, str]:
    if config.get("status") != "frozen_descriptive_e5_after_e4_lock":
        raise RuntimeError("E5 concentration config is not frozen")
    if sha256_file(Path(__file__).resolve()) != config["runner"]["sha256"]:
        raise RuntimeError("E5 concentration runner differs from frozen config")
    verified = {}
    for name, entry in config["inputs"].items():
        path = root_path(entry["path"])
        actual = sha256_file(path)
        if actual != entry["sha256"]:
            raise RuntimeError(f"E5 input hash mismatch: {name}: {actual}")
        verified[name] = actual
    return verified


def domain_from_source_task_id(value: str) -> str:
    match = re.match(r"^test_public_v2_([^_]+)_", value)
    if match is None:
        raise RuntimeError(f"cannot derive frozen task domain: {value}")
    return match.group(1)


def paired_row(
    index: Mapping[tuple[str, str, str], Mapping[str, Any]],
    *,
    model: str,
    baseline: str,
    treatment: str,
    target_keys: list[str],
) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    for key in target_keys:
        left = bool(index[(model, key, baseline)]["outcome"]["recovery_validity"])
        right = bool(index[(model, key, treatment)]["outcome"]["recovery_validity"])
        counts["baseline_successes"] += left
        counts["treatment_successes"] += right
        counts["positive_discordant"] += (not left) and right
        counts["negative_discordant"] += left and (not right)
    n = len(target_keys)
    return {
        "n": n,
        "baseline_successes": counts["baseline_successes"],
        "treatment_successes": counts["treatment_successes"],
        "positive_discordant": counts["positive_discordant"],
        "negative_discordant": counts["negative_discordant"],
        "net_success_gain": counts["treatment_successes"] - counts["baseline_successes"],
        "paired_risk_difference": (
            (counts["treatment_successes"] - counts["baseline_successes"]) / n
            if n
            else None
        ),
    }


def hhi(values: list[int]) -> float | None:
    total = sum(values)
    if total == 0:
        return None
    return sum((value / total) ** 2 for value in values)


def concentration_for(
    index: Mapping[tuple[str, str, str], Mapping[str, Any]],
    *,
    model: str,
    comparison: Mapping[str, Any],
    target_keys: list[str],
    groups: Mapping[str, Mapping[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    group_rows = []
    leave_one_out_rows = []
    summaries = []
    full = paired_row(
        index,
        model=model,
        baseline=comparison["baseline"],
        treatment=comparison["treatment"],
        target_keys=target_keys,
    )
    for group_type in comparison["group_types"]:
        values = sorted({groups[key][group_type] for key in target_keys})
        typed_rows = []
        typed_loo = []
        for value in values:
            members = [key for key in target_keys if groups[key][group_type] == value]
            row = {
                "comparison": comparison["name"],
                "model_name": model,
                "group_type": group_type,
                "group_value": value,
                **paired_row(
                    index,
                    model=model,
                    baseline=comparison["baseline"],
                    treatment=comparison["treatment"],
                    target_keys=members,
                ),
            }
            typed_rows.append(row)
            remaining = [key for key in target_keys if groups[key][group_type] != value]
            if remaining:
                typed_loo.append(
                    {
                        "comparison": comparison["name"],
                        "model_name": model,
                        "left_out_group_type": group_type,
                        "left_out_group_value": value,
                        **paired_row(
                            index,
                            model=model,
                            baseline=comparison["baseline"],
                            treatment=comparison["treatment"],
                            target_keys=remaining,
                        ),
                    }
                )
        group_rows.extend(typed_rows)
        leave_one_out_rows.extend(typed_loo)
        positive = [item["positive_discordant"] for item in typed_rows]
        discordant = [
            item["positive_discordant"] + item["negative_discordant"]
            for item in typed_rows
        ]
        loo_effects = [item["paired_risk_difference"] for item in typed_loo]
        summaries.append(
            {
                "comparison": comparison["name"],
                "model_name": model,
                "group_type": group_type,
                "group_count": len(values),
                "full_n": full["n"],
                "full_paired_risk_difference": full["paired_risk_difference"],
                "positive_transfer_hhi": hhi(positive),
                "discordance_hhi": hhi(discordant),
                "largest_positive_transfer_share": (
                    max(positive) / sum(positive) if sum(positive) else None
                ),
                "largest_discordance_share": (
                    max(discordant) / sum(discordant) if sum(discordant) else None
                ),
                "positive_net_group_count": sum(item["net_success_gain"] > 0 for item in typed_rows),
                "negative_net_group_count": sum(item["net_success_gain"] < 0 for item in typed_rows),
                "zero_net_group_count": sum(item["net_success_gain"] == 0 for item in typed_rows),
                "leave_one_out_min_risk_difference": min(loo_effects) if loo_effects else None,
                "leave_one_out_max_risk_difference": max(loo_effects) if loo_effects else None,
                "leave_one_out_sign_reversal_count": sum(
                    effect is not None
                    and full["paired_risk_difference"] is not None
                    and effect * full["paired_risk_difference"] <= 0
                    for effect in loo_effects
                ),
            }
        )
    return group_rows, leave_one_out_rows, summaries


def analyze(config: Mapping[str, Any], verified: Mapping[str, str]) -> tuple[dict[str, Any], dict[str, Any]]:
    evaluation = read_json(root_path(config["inputs"]["evaluation_results"]["path"]))
    selection_payload = read_json(root_path(config["inputs"]["selection_manifest"]["path"]))
    deterministic_payload = read_json(
        root_path(config["inputs"]["deterministic_selections"]["path"])
    )
    observable_payload = read_json(root_path(config["inputs"]["observable_inputs"]["path"]))
    records = evaluation["records"]
    if len(records) != int(config["expected"]["logical_rows"]):
        raise RuntimeError("E5 evaluation row count mismatch")
    index = {
        (item["model_name"], item["target_key"], item["condition"]): item
        for item in records
    }
    selection = {item["target_key"]: item for item in selection_payload["records"]}
    deterministic = {
        item["target_key"]: item for item in deterministic_payload["records"]
    }
    observable = {item["target_key"]: item for item in observable_payload["targets"]}
    groups = {
        key: {
            "stratum": selection[key]["stratum"],
            "failed_tool": observable[key]["judge_context"]["failed_tool_name"],
            "task_domain": domain_from_source_task_id(deterministic[key]["source_task_id"]),
            "proper_selected_memory": selection[key]["selections"]["proper"][
                "selected_memory_key"
            ],
        }
        for key in sorted(selection)
    }

    all_group_rows = []
    all_loo_rows = []
    all_summaries = []
    population_counts = {}
    for comparison in config["comparisons"]:
        if comparison["population"] == "changed_target_union":
            targets = [key for key in sorted(selection) if selection[key]["changed_target_union_member"]]
        elif comparison["population"] == "gate_interventions":
            targets = [
                key
                for key in sorted(selection)
                if selection[key]["selections"]["proper"]["selected_memory_key"]
                != selection[key]["selections"]["proper_no_gate"]["selected_memory_key"]
            ]
        else:
            raise RuntimeError(f"unsupported E5 population: {comparison['population']}")
        population_counts[comparison["name"]] = len(targets)
        for model in config["models"]:
            group_rows, loo_rows, summaries = concentration_for(
                index,
                model=model,
                comparison=comparison,
                target_keys=targets,
                groups=groups,
            )
            all_group_rows.extend(group_rows)
            all_loo_rows.extend(loo_rows)
            all_summaries.extend(summaries)

    headline = {}
    for item in all_summaries:
        if item["comparison"] == "primary_proper_vs_tfidf" and item["group_type"] in {
            "failed_tool",
            "task_domain",
        }:
            prefix = f"{item['model_name']}:{item['group_type']}"
            headline[f"{prefix}:largest_positive_transfer_share"] = item[
                "largest_positive_transfer_share"
            ]
            headline[f"{prefix}:leave_one_out_min_risk_difference"] = item[
                "leave_one_out_min_risk_difference"
            ]
            headline[f"{prefix}:leave_one_out_sign_reversal_count"] = item[
                "leave_one_out_sign_reversal_count"
            ]
    output = {
        "schema_version": 1,
        "stage_id": "e5_effect_concentration",
        "status": "complete_descriptive_no_method_changes",
        "input_identities": dict(verified),
        "population_counts": population_counts,
        "headline": dict(sorted(headline.items())),
        "concentration_summaries": all_summaries,
        "group_rows": all_group_rows,
        "leave_one_group_out_rows": all_loo_rows,
        "interpretation_boundary": config["interpretation_boundary"],
    }
    audit = {
        "schema_version": 1,
        "stage_id": "e5_effect_concentration",
        "status": "passed",
        "checks": {
            "all_inputs_hash_verified": True,
            "same_target_pairing": True,
            "groups_derived_without_model_outputs": True,
            "leave_one_group_out_is_exclusion_sensitivity_not_retraining": True,
            "no_new_inference_or_environment_execution": True,
            "no_method_or_population_change": True,
        },
        "counts": {
            "logical_rows": len(records),
            "group_rows": len(all_group_rows),
            "leave_one_group_out_rows": len(all_loo_rows),
            "summary_rows": len(all_summaries),
        },
    }
    return output, audit


def main() -> None:
    parser = argparse.ArgumentParser(description="Frozen E5 effect concentration analysis.")
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()
    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    verified = verify(config)
    output, audit = analyze(config, verified)
    write_json(root_path(config["outputs"]["concentration"]), output)
    write_json(root_path(config["outputs"]["audit"]), audit)
    print(json.dumps(output["headline"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
