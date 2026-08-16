from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs" / "paper_2026" / "e4_diagnostics_v1_0.yaml"


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


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def verify(config: Mapping[str, Any]) -> dict[str, str]:
    if config.get("status") != "frozen_descriptive_e4_after_e2_e3_lock":
        raise RuntimeError("E4 diagnostic config is not frozen")
    if sha256_file(Path(__file__).resolve()) != config["runner"]["sha256"]:
        raise RuntimeError("E4 diagnostic runner differs from frozen config")
    verified = {}
    for name, entry in config["inputs"].items():
        path = root_path(entry["path"])
        actual = sha256_file(path)
        if actual != entry["sha256"]:
            raise RuntimeError(f"E4 input hash mismatch: {name}: {actual}")
        verified[name] = actual
    return verified


def paired_counts(
    index: Mapping[tuple[str, str, str], Mapping[str, Any]],
    *,
    model: str,
    baseline: str,
    treatment: str,
    target_keys: Iterable[str],
) -> dict[str, Any]:
    counters: Counter[str] = Counter()
    targets = list(target_keys)
    for target_key in targets:
        left = index[(model, target_key, baseline)]
        right = index[(model, target_key, treatment)]
        left_valid = bool(left["outcome"]["recovery_validity"])
        right_valid = bool(right["outcome"]["recovery_validity"])
        counters["baseline_successes"] += left_valid
        counters["treatment_successes"] += right_valid
        counters["positive_transfer"] += (not left_valid) and right_valid
        counters["negative_transfer"] += left_valid and (not right_valid)
        counters["decision_changed"] += canonical(left["decision"]) != canonical(right["decision"])
        counters["parse_failure_introduced"] += left["parse_valid"] and (not right["parse_valid"])
        counters["parse_failure_removed"] += (not left["parse_valid"]) and right["parse_valid"]
        counters["additional_tool_call"] += (
            right["outcome"]["recovery_tool_calls"] > left["outcome"]["recovery_tool_calls"]
        )
        counters["additional_repeated_invalid_call"] += (
            right["outcome"]["repeated_invalid_calls"]
            > left["outcome"]["repeated_invalid_calls"]
        )
        counters["safety_regression"] += (
            (not left["outcome"]["safety_violation"])
            and right["outcome"]["safety_violation"]
        )
    return {
        "n": len(targets),
        **dict(sorted(counters.items())),
        "paired_risk_difference": (
            counters["treatment_successes"] - counters["baseline_successes"]
        )
        / len(targets),
    }


def target_groups(
    target_meta: Mapping[str, Mapping[str, Any]], population: str, stratum: str
) -> list[str]:
    return [
        key
        for key, value in sorted(target_meta.items())
        if (population == "all_valid_targets" or value["union"])
        and (stratum == "all_strata" or value["stratum"] == stratum)
    ]


def risk_diagnostics(
    config: Mapping[str, Any],
    index: Mapping[tuple[str, str, str], Mapping[str, Any]],
    target_meta: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    comparisons = tuple(config["risk_comparisons"])
    for model in config["models"]:
        for population in config["populations"]:
            for stratum in ("all_strata", *config["strata"]):
                targets = target_groups(target_meta, population, stratum)
                for item in comparisons:
                    rows.append(
                        {
                            "model_name": model,
                            "population": population,
                            "stratum": stratum,
                            "baseline": item["baseline"],
                            "treatment": item["treatment"],
                            **paired_counts(
                                index,
                                model=model,
                                baseline=item["baseline"],
                                treatment=item["treatment"],
                                target_keys=targets,
                            ),
                        }
                    )
    return rows


def intervention_rows(
    config: Mapping[str, Any],
    index: Mapping[tuple[str, str, str], Mapping[str, Any]],
    selection: Mapping[str, Mapping[str, Any]],
    target_meta: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for diagnostic in config["interventions"]:
        baseline = diagnostic["baseline"]
        treatment = diagnostic["treatment"]
        selected_targets = [
            key
            for key, record in sorted(selection.items())
            if record["selections"][baseline]["selected_memory_key"]
            != record["selections"][treatment]["selected_memory_key"]
        ]
        for model in config["models"]:
            for stratum in ("all_strata", *config["strata"]):
                targets = [
                    key
                    for key in selected_targets
                    if stratum == "all_strata" or target_meta[key]["stratum"] == stratum
                ]
                if not targets:
                    continue
                rows.append(
                    {
                        "intervention": diagnostic["name"],
                        "model_name": model,
                        "stratum": stratum,
                        "selection_changed_target_count": len(targets),
                        **paired_counts(
                            index,
                            model=model,
                            baseline=baseline,
                            treatment=treatment,
                            target_keys=targets,
                        ),
                    }
                )
    return rows


def applicability_rows(
    config: Mapping[str, Any], records: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    output = []
    for model in config["models"]:
        for condition in config["memory_conditions"]:
            for applicable in (False, True):
                values = [
                    item
                    for item in records
                    if item["model_name"] == model
                    and item["condition"] == condition
                    and item["selection_applicable"] is applicable
                ]
                n = len(values)
                output.append(
                    {
                        "model_name": model,
                        "condition": condition,
                        "selection_applicable": applicable,
                        "n": n,
                        "recovery_validity_count": sum(
                            item["outcome"]["recovery_validity"] for item in values
                        ),
                        "recovery_validity_rate": (
                            sum(item["outcome"]["recovery_validity"] for item in values) / n
                            if n
                            else None
                        ),
                        "parse_failure_count": sum(not item["parse_valid"] for item in values),
                        "repeated_invalid_calls_count": sum(
                            item["outcome"]["repeated_invalid_calls"] for item in values
                        ),
                    }
                )
    return output


def failure_reason(record: Mapping[str, Any], failed_tool_name: str) -> str:
    if not record["parse_valid"]:
        return "invalid_model_output"
    if record["outcome"]["recovery_validity"]:
        return "recovery_success"
    if record["decision"]["kind"] == "stop":
        return "model_stop"
    if record["decision"].get("tool_name") != failed_tool_name:
        return "different_tool"
    if record["second_error_code"] is not None:
        return f"same_tool_second_error:{record['second_error_code']}"
    if not record["outcome"]["task_completion"]:
        return "same_tool_no_error_task_incomplete"
    return "other_invalid_recovery"


def execution_failure_rows(
    config: Mapping[str, Any],
    records: list[dict[str, Any]],
    observable: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], Counter[str]] = defaultdict(Counter)
    for record in records:
        failed_tool = observable[record["target_key"]]["judge_context"]["failed_tool_name"]
        grouped[(record["model_name"], record["condition"], record["stratum"])][
            failure_reason(record, failed_tool)
        ] += 1
    output = []
    for (model, condition, stratum), counts in sorted(grouped.items()):
        output.append(
            {
                "model_name": model,
                "condition": condition,
                "stratum": stratum,
                "n": sum(counts.values()),
                "reason_counts": dict(sorted(counts.items())),
            }
        )
    return output


def reason_code_rows(
    config: Mapping[str, Any], deterministic: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    rows = []
    for variant in config["proper_variants"]:
        counts: Counter[str] = Counter()
        action_counts: Counter[str] = Counter()
        for record in deterministic.values():
            value = record["proper_variants"][variant]
            action_counts[value["action"]] += 1
            counts.update(value["reason_codes"])
        rows.append(
            {
                "variant": variant,
                "action_counts": dict(sorted(action_counts.items())),
                "reason_code_counts": dict(sorted(counts.items())),
            }
        )
    return rows


def markdown_report(payload: Mapping[str, Any]) -> str:
    headline = payload["headline"]
    lines = [
        "# E4 risk and mechanism diagnostics",
        "",
        "This stage is descriptive and explanatory. It does not alter any frozen method, threshold, prompt, or model output.",
        "",
        "## Locked headline findings",
        "",
    ]
    for key, value in headline.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "- Negative transfer is a paired No-Memory-success / memory-condition-failure event.",
            "- Intervention diagnostics are restricted to targets where the compared selectors chose different memory identities.",
            "- These diagnostics explain the frozen E2/E3 results and are not additional confirmatory tests.",
            "- No malformed output is repaired and no condition is selectively regenerated.",
            "",
        ]
    )
    return "\n".join(lines)


def diagnose(config: Mapping[str, Any], verified: Mapping[str, str]) -> tuple[dict[str, Any], dict[str, Any]]:
    evaluation = read_json(root_path(config["inputs"]["evaluation_results"]["path"]))
    selection_payload = read_json(root_path(config["inputs"]["selection_manifest"]["path"]))
    deterministic_payload = read_json(
        root_path(config["inputs"]["deterministic_selections"]["path"])
    )
    observable_payload = read_json(root_path(config["inputs"]["observable_inputs"]["path"]))
    records = evaluation["records"]
    if len(records) != int(config["expected"]["logical_rows"]):
        raise RuntimeError("E4 evaluation row count mismatch")
    index = {
        (item["model_name"], item["target_key"], item["condition"]): item
        for item in records
    }
    if len(index) != len(records):
        raise RuntimeError("E4 encountered duplicate logical-row identity")
    selection = {item["target_key"]: item for item in selection_payload["records"]}
    deterministic = {
        item["target_key"]: item for item in deterministic_payload["records"]
    }
    observable = {item["target_key"]: item for item in observable_payload["targets"]}
    target_meta = {
        item["target_key"]: {
            "stratum": item["stratum"],
            "union": item["changed_target_union_member"],
        }
        for item in selection_payload["records"]
    }

    risk = risk_diagnostics(config, index, target_meta)
    interventions = intervention_rows(config, index, selection, target_meta)
    applicability = applicability_rows(config, records)
    failures = execution_failure_rows(config, records, observable)
    reasons = reason_code_rows(config, deterministic)

    def risk_row(model: str, treatment: str) -> dict[str, Any]:
        return next(
            item
            for item in risk
            if item["model_name"] == model
            and item["population"] == "changed_target_union"
            and item["stratum"] == "all_strata"
            and item["baseline"] == "no_memory"
            and item["treatment"] == treatment
        )

    qwen_proper = risk_row("qwen3_8b", "proper")
    mistral_proper = risk_row("mistral_7b_instruct_v0_3", "proper")
    gate_rows = {
        item["model_name"]: item
        for item in interventions
        if item["intervention"] == "gate_component"
        and item["stratum"] == "all_strata"
    }
    contradiction_rows = {
        item["model_name"]: item
        for item in interventions
        if item["intervention"] == "contradiction_component"
        and item["stratum"] == "all_strata"
    }
    headline = {
        "qwen_proper_vs_no_memory_risk_difference": qwen_proper["paired_risk_difference"],
        "qwen_proper_negative_transfer_count": qwen_proper["negative_transfer"],
        "mistral_proper_vs_no_memory_risk_difference": mistral_proper[
            "paired_risk_difference"
        ],
        "mistral_proper_negative_transfer_count": mistral_proper["negative_transfer"],
        "gate_selection_changed_targets": gate_rows["qwen3_8b"][
            "selection_changed_target_count"
        ],
        "gate_qwen_paired_risk_difference_on_interventions": gate_rows["qwen3_8b"][
            "paired_risk_difference"
        ],
        "gate_mistral_paired_risk_difference_on_interventions": gate_rows[
            "mistral_7b_instruct_v0_3"
        ]["paired_risk_difference"],
        "contradiction_selection_changed_targets": contradiction_rows["qwen3_8b"][
            "selection_changed_target_count"
        ],
        "contradiction_qwen_paired_risk_difference_on_interventions": contradiction_rows[
            "qwen3_8b"
        ]["paired_risk_difference"],
        "contradiction_mistral_paired_risk_difference_on_interventions": contradiction_rows[
            "mistral_7b_instruct_v0_3"
        ]["paired_risk_difference"],
    }
    diagnostics = {
        "schema_version": 1,
        "stage_id": "e4_risk_and_mechanism_diagnostics",
        "status": "complete_descriptive_no_method_changes",
        "input_identities": dict(verified),
        "headline": headline,
        "risk_rows": risk,
        "intervention_rows": interventions,
        "applicability_rows": applicability,
        "execution_failure_rows": failures,
        "selector_reason_rows": reasons,
        "interpretation_boundary": config["interpretation_boundary"],
    }
    audit = {
        "schema_version": 1,
        "stage_id": "e4_risk_and_mechanism_diagnostics",
        "status": "passed",
        "checks": {
            "all_inputs_hash_verified": True,
            "all_logical_rows_present": True,
            "paired_negative_transfer_uses_same_target": True,
            "interventions_require_different_memory_identity": True,
            "invalid_outputs_retained": True,
            "no_new_inference_or_environment_execution": True,
            "no_method_threshold_or_prompt_change": True,
        },
        "counts": {
            "logical_rows": len(records),
            "risk_rows": len(risk),
            "intervention_rows": len(interventions),
            "applicability_rows": len(applicability),
            "execution_failure_rows": len(failures),
        },
    }
    return diagnostics, audit


def main() -> None:
    parser = argparse.ArgumentParser(description="Frozen descriptive E4 diagnostics.")
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()
    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    verified = verify(config)
    diagnostics, audit = diagnose(config, verified)
    write_json(root_path(config["outputs"]["diagnostics"]), diagnostics)
    write_json(root_path(config["outputs"]["audit"]), audit)
    report_path = root_path(config["outputs"]["report"])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(markdown_report(diagnostics), encoding="utf-8")
    print(json.dumps(diagnostics["headline"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
