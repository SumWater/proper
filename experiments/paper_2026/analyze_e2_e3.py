from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping

import yaml


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs" / "paper_2026" / "e2_e3_analysis_v1_0.yaml"
sys.path.insert(0, str(ROOT / "src"))

from failure_memory.paper_2026.statistics import (  # noqa: E402
    derived_seed,
    holm_adjust,
    paired_binary_summary,
    paired_bootstrap_risk_difference_ci,
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


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def verify(config: Mapping[str, Any]) -> dict[str, str]:
    if config.get("status") != "frozen_before_formal_e2_e3_analysis":
        raise RuntimeError("E2/E3 analysis config is not frozen")
    if sha256_file(Path(__file__).resolve()) != config["runner"]["sha256"]:
        raise RuntimeError("E2/E3 analysis runner differs from frozen config")
    verified = {}
    for name, entry in config["inputs"].items():
        path = root_path(entry["path"])
        actual = sha256_file(path)
        if actual != entry["sha256"]:
            raise RuntimeError(f"E2/E3 analysis input hash mismatch: {name}: {actual}")
        verified[name] = actual
    return verified


def paired_values(
    index: Mapping[tuple[str, str, str], Mapping[str, Any]],
    *,
    model: str,
    baseline: str,
    treatment: str,
    target_keys: list[str],
    endpoint: str,
) -> tuple[list[int], list[int]]:
    left = []
    right = []
    for target_key in target_keys:
        left.append(int(index[(model, target_key, baseline)]["outcome"][endpoint]))
        right.append(int(index[(model, target_key, treatment)]["outcome"][endpoint]))
    return left, right


def comparison(
    index: Mapping[tuple[str, str, str], Mapping[str, Any]],
    *,
    family: str,
    model: str,
    baseline: str,
    treatment: str,
    target_keys: list[str],
    endpoint: str,
    config: Mapping[str, Any],
    stratum: str | None = None,
    population: str,
) -> dict[str, Any]:
    analysis_id = ":".join(
        value
        for value in (family, model, population, stratum or "all_strata", treatment, baseline, endpoint)
    )
    left, right = paired_values(
        index,
        model=model,
        baseline=baseline,
        treatment=treatment,
        target_keys=target_keys,
        endpoint=endpoint,
    )
    summary = paired_binary_summary(left, right).to_mapping()
    lower, upper = paired_bootstrap_risk_difference_ci(
        left,
        right,
        replicates=int(config["bootstrap"]["replicates"]),
        confidence_level=float(config["bootstrap"]["confidence_level"]),
        seed=derived_seed(int(config["bootstrap"]["base_seed"]), analysis_id),
    )
    return {
        "analysis_id": analysis_id,
        "family": family,
        "model_name": model,
        "population": population,
        "stratum": stratum or "all_strata",
        "endpoint": endpoint,
        "baseline": baseline,
        "treatment": treatment,
        **summary,
        "paired_bootstrap_ci": {
            "confidence_level": config["bootstrap"]["confidence_level"],
            "lower": lower,
            "upper": upper,
            "replicates": config["bootstrap"]["replicates"],
        },
    }


def apply_holm(rows: list[dict[str, Any]]) -> None:
    families: dict[str, dict[str, float]] = defaultdict(dict)
    for row in rows:
        families[row["family"]][row["analysis_id"]] = row["exact_two_sided_mcnemar_p"]
    adjusted = {family: holm_adjust(values) for family, values in families.items()}
    for row in rows:
        row["holm_adjusted_p"] = adjusted[row["family"]][row["analysis_id"]]
        row["significant_at_alpha"] = row["holm_adjusted_p"] <= 0.05


def descriptive_rows(records: list[dict[str, Any]], models: list[str], conditions: list[str]) -> list[dict[str, Any]]:
    output = []
    for model in models:
        for population in ("changed_target_union", "all_valid_targets"):
            for stratum in ("all_strata", "argument_omission", "transient_authorization", "timeout"):
                for condition in conditions:
                    values = [
                        item
                        for item in records
                        if item["model_name"] == model
                        and item["condition"] == condition
                        and (population == "all_valid_targets" or item["changed_target_union_member"])
                        and (stratum == "all_strata" or item["stratum"] == stratum)
                    ]
                    if not values:
                        continue
                    n = len(values)
                    output.append(
                        {
                            "model_name": model,
                            "population": population,
                            "stratum": stratum,
                            "condition": condition,
                            "n": n,
                            "recovery_validity_count": sum(item["outcome"]["recovery_validity"] for item in values),
                            "recovery_validity_rate": sum(item["outcome"]["recovery_validity"] for item in values) / n,
                            "task_completion_count": sum(item["outcome"]["task_completion"] for item in values),
                            "safety_violation_count": sum(item["outcome"]["safety_violation"] for item in values),
                            "repeated_invalid_calls_count": sum(item["outcome"]["repeated_invalid_calls"] for item in values),
                            "recovery_tool_calls": sum(item["outcome"]["recovery_tool_calls"] for item in values),
                            "parse_failure_count": sum(not item["parse_valid"] for item in values),
                        }
                    )
    return output


def analyze(config: Mapping[str, Any], verified: Mapping[str, str]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    results = json.loads(root_path(config["inputs"]["evaluation_results"]["path"]).read_text(encoding="utf-8"))
    records = results["records"]
    if len(records) != int(config["expected"]["logical_rows"]):
        raise RuntimeError("formal evaluation logical-row count mismatch")
    index = {
        (item["model_name"], item["target_key"], item["condition"]): item
        for item in records
    }
    if len(index) != len(records):
        raise RuntimeError("duplicate formal evaluation row identity")
    target_meta = {}
    for item in records:
        target_meta[item["target_key"]] = {
            "stratum": item["stratum"],
            "union": item["changed_target_union_member"],
        }
    all_targets = sorted(target_meta)
    union_targets = [key for key in all_targets if target_meta[key]["union"]]
    if len(union_targets) != int(config["expected"]["changed_target_union"]):
        raise RuntimeError("changed-target union count mismatch")

    rows: list[dict[str, Any]] = []
    endpoint = config["endpoint"]
    for model in config["models"]:
        for spec in config["confirmatory_comparisons"]:
            rows.append(
                comparison(
                    index,
                    family=spec["family"],
                    model=model,
                    baseline=spec["baseline"],
                    treatment=spec["treatment"],
                    target_keys=union_targets,
                    endpoint=endpoint,
                    config=config,
                    population="changed_target_union",
                )
            )
        rows.append(
            comparison(
                index,
                family="all_valid_sensitivity",
                model=model,
                baseline="tfidf",
                treatment="proper",
                target_keys=all_targets,
                endpoint=endpoint,
                config=config,
                population="all_valid_targets",
            )
        )
        for stratum in config["strata"]:
            stratum_targets = [
                key for key in union_targets if target_meta[key]["stratum"] == stratum
            ]
            rows.append(
                comparison(
                    index,
                    family="stratified_primary_exploratory",
                    model=model,
                    baseline="tfidf",
                    treatment="proper",
                    target_keys=stratum_targets,
                    endpoint=endpoint,
                    config=config,
                    stratum=stratum,
                    population="changed_target_union",
                )
            )
    apply_holm(rows)
    rows.sort(key=lambda item: item["analysis_id"])

    descriptive = descriptive_rows(records, list(config["models"]), list(config["conditions"]))
    primary = [item for item in rows if item["family"] == "primary_proper_vs_tfidf"]
    analysis = {
        "schema_version": 1,
        "stage_id": "e2_e3_formal_analysis",
        "status": "complete",
        "input_identities": dict(verified),
        "endpoint": endpoint,
        "inference": {
            "comparisons": rows,
            "family_count": len({item["family"] for item in rows}),
            "comparison_count": len(rows),
            "multiplicity": "Holm correction within each pre-frozen family",
        },
        "primary_direction_summary": [
            {
                "model_name": item["model_name"],
                "paired_risk_difference": item["paired_risk_difference"],
                "holm_adjusted_p": item["holm_adjusted_p"],
                "ci_lower": item["paired_bootstrap_ci"]["lower"],
                "ci_upper": item["paired_bootstrap_ci"]["upper"],
                "direction": (
                    "proper_better" if item["paired_risk_difference"] > 0
                    else "proper_worse" if item["paired_risk_difference"] < 0
                    else "tie"
                ),
            }
            for item in primary
        ],
        "interpretation_boundary": {
            "invalid_outputs_are_intention_to_treat_failures": True,
            "oracle_is_descriptive_only": True,
            "stratified_tests_are_exploratory": True,
            "all_valid_population_is_sensitivity_only": True,
        },
    }
    tables = {
        "schema_version": 1,
        "stage_id": "e2_e3_formal_analysis",
        "descriptive_rows": descriptive,
        "inference_rows": rows,
    }
    audit = {
        "schema_version": 1,
        "stage_id": "e2_e3_formal_analysis",
        "status": "passed",
        "checks": {
            "frozen_inputs_verified": True,
            "paired_row_identity_unique": True,
            "primary_population_is_changed_target_union": True,
            "exact_two_sided_mcnemar": True,
            "paired_bootstrap_deterministic": True,
            "holm_within_prefrozen_families": True,
            "invalid_outputs_retained": True,
            "no_model_output_regeneration_or_method_change": True,
        },
        "counts": {
            "logical_rows": len(records),
            "target_count": len(all_targets),
            "changed_target_union": len(union_targets),
            "comparison_count": len(rows),
            "descriptive_row_count": len(descriptive),
        },
    }
    return analysis, tables, audit


def main() -> None:
    parser = argparse.ArgumentParser(description="Frozen formal E2/E3 paired analysis.")
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()
    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    verified = verify(config)
    analysis, tables, audit = analyze(config, verified)
    write_json(root_path(config["outputs"]["analysis"]), analysis)
    write_json(root_path(config["outputs"]["tables"]), tables)
    write_json(root_path(config["outputs"]["audit"]), audit)
    print(json.dumps(analysis["primary_direction_summary"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
