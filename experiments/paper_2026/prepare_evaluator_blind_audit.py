"""Prepare the frozen, method-blinded evaluator audit packet.

This stage reads only already-frozen formal outputs.  It never loads a model,
executes an environment, or reads human labels.  The reviewer packet omits
model, target, condition, treatment/baseline, and computed endpoint identities.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "configs" / "paper_2026" / "evaluator_blind_audit_v1_0.yaml"
OBSERVATION_MARKER = "AGENT_VISIBLE_OBSERVATION="


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def root_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def stable_hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def verify_inputs(config: Mapping[str, Any]) -> dict[str, str]:
    verified: dict[str, str] = {}
    for name, item in config["inputs"].items():
        path = root_path(item["path"])
        observed = sha256_file(path)
        if observed != str(item["sha256"]):
            raise RuntimeError(f"input hash mismatch for {name}: {observed}")
        verified[name] = observed
    return verified


def extract_observation(prompt: str) -> dict[str, Any]:
    for line in prompt.splitlines():
        if line.startswith(OBSERVATION_MARKER):
            value = json.loads(line[len(OBSERVATION_MARKER) :])
            if not isinstance(value, dict):
                raise RuntimeError("agent-visible observation is not an object")
            return value
    raise RuntimeError("agent-visible observation marker is absent")


def eligible_treatment_rows(
    comparison: Mapping[str, Any], records: Iterable[Mapping[str, Any]]
) -> Iterable[Mapping[str, Any]]:
    for record in records:
        if record["model_name"] != comparison["model_name"]:
            continue
        if record["condition"] != comparison["treatment"]:
            continue
        if comparison["population"] == "changed_target_union" and not record[
            "changed_target_union_member"
        ]:
            continue
        if comparison["stratum"] != "all_strata" and record["stratum"] != comparison["stratum"]:
            continue
        yield record


def prepare(config: Mapping[str, Any], verified: Mapping[str, str]) -> dict[str, Any]:
    evaluation = read_json(root_path(config["inputs"]["evaluation_results"]["path"]))
    analysis = read_json(root_path(config["inputs"]["formal_analysis"]["path"]))
    prompts = read_json(root_path(config["inputs"]["prompt_manifest"]["path"]))
    records = evaluation["records"]
    by_record = {
        (row["model_name"], row["target_key"], row["condition"]): row for row in records
    }
    if len(by_record) != len(records):
        raise RuntimeError("evaluation records are not unique")

    prompt_by_hash = {row["prompt_sha256"]: row for row in prompts["unique_prompts"]}
    observation_by_target: dict[str, dict[str, Any]] = {}
    for target in prompts["target_records"]:
        prompt_hash = target["conditions"]["no_memory"]["prompt_sha256"]
        prompt = prompt_by_hash[prompt_hash]["prompt"]
        observation_by_target[target["target_key"]] = extract_observation(prompt)

    pair_universe: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for comparison in sorted(analysis["inference"]["comparisons"], key=lambda row: row["analysis_id"]):
        for treatment in eligible_treatment_rows(comparison, records):
            key = (
                comparison["model_name"],
                treatment["target_key"],
                comparison["treatment"],
                comparison["baseline"],
            )
            baseline = by_record[(key[0], key[1], key[3])]
            entry = pair_universe.setdefault(
                key,
                {
                    "treatment": treatment,
                    "baseline": baseline,
                    "analysis_ids": [],
                    "families": [],
                    "populations": [],
                },
            )
            if entry["treatment"]["outcome"] != treatment["outcome"]:
                raise RuntimeError("overlapping comparison treatment outcomes differ")
            entry["analysis_ids"].append(comparison["analysis_id"])
            entry["families"].append(comparison["family"])
            entry["populations"].append(comparison["population"])

    discordant: list[tuple[tuple[str, str, str, str], dict[str, Any]]] = []
    non_discordant: dict[
        tuple[str, str, str, str], list[tuple[tuple[str, str, str, str], dict[str, Any]]]
    ] = defaultdict(list)
    for key, entry in sorted(pair_universe.items()):
        treatment_value = bool(entry["treatment"]["outcome"]["recovery_validity"])
        baseline_value = bool(entry["baseline"]["outcome"]["recovery_validity"])
        pair = (key, entry)
        if treatment_value != baseline_value:
            discordant.append(pair)
        else:
            group = (key[0], key[2], key[3], entry["treatment"]["stratum"])
            non_discordant[group].append(pair)

    seed = str(config["sampling"]["seed"])
    fraction = float(config["sampling"]["non_discordant_fraction"])
    sampled_non_discordant: list[tuple[tuple[str, str, str, str], dict[str, Any]]] = []
    stratum_sampling: list[dict[str, Any]] = []
    for group, values in sorted(non_discordant.items()):
        ranked = sorted(values, key=lambda item: stable_hash(seed, *item[0]))
        sample_n = math.ceil(fraction * len(ranked))
        sampled_non_discordant.extend(ranked[:sample_n])
        stratum_sampling.append(
            {
                "model_name": group[0],
                "treatment": group[1],
                "baseline": group[2],
                "failure_stratum": group[3],
                "non_discordant_population_n": len(ranked),
                "sample_n": sample_n,
            }
        )

    selected = [("all_discordant", item) for item in discordant] + [
        ("sampled_non_discordant", item) for item in sampled_non_discordant
    ]
    selected.sort(key=lambda item: stable_hash(seed, *item[1][0]))

    reviewer_rows: list[dict[str, Any]] = []
    key_rows: list[dict[str, Any]] = []
    seen_pair_ids: set[str] = set()
    side_counts: Counter[str] = Counter()
    for inclusion_reason, (key, entry) in selected:
        pair_id = "BRP-" + stable_hash(seed, "pair-id", *key)[:16].upper()
        if pair_id in seen_pair_ids:
            raise RuntimeError("blind pair id collision")
        seen_pair_ids.add(pair_id)
        treatment_on_a = int(stable_hash(seed, "side", *key), 16) % 2 == 0
        side_counts["treatment_on_a" if treatment_on_a else "treatment_on_b"] += 1
        side_a_name, side_b_name = (
            ("treatment", "baseline") if treatment_on_a else ("baseline", "treatment")
        )
        side_a = entry[side_a_name]
        side_b = entry[side_b_name]

        def blinded_side(row: Mapping[str, Any]) -> dict[str, Any]:
            return {
                "decision": row["decision"],
                "parse_valid": bool(row["parse_valid"]),
                "second_error_code": row["second_error_code"],
                "task_completion": bool(row["outcome"]["task_completion"]),
                "safety_violation": bool(row["outcome"]["safety_violation"]),
                "repeated_invalid_calls": int(row["outcome"]["repeated_invalid_calls"]),
            }

        reviewer_rows.append(
            {
                "pair_id": pair_id,
                "failure_stratum": entry["treatment"]["stratum"],
                "agent_visible_observation": observation_by_target[key[1]],
                "decision_a": blinded_side(side_a),
                "decision_b": blinded_side(side_b),
            }
        )
        key_rows.append(
            {
                "pair_id": pair_id,
                "inclusion_reason": inclusion_reason,
                "model_name": key[0],
                "target_key": key[1],
                "instance_id": entry["treatment"]["instance_id"],
                "failure_stratum": entry["treatment"]["stratum"],
                "treatment_condition": key[2],
                "baseline_condition": key[3],
                "side_a_identity": side_a_name,
                "side_b_identity": side_b_name,
                "side_a_automated_recovery_validity": bool(
                    side_a["outcome"]["recovery_validity"]
                ),
                "side_b_automated_recovery_validity": bool(
                    side_b["outcome"]["recovery_validity"]
                ),
                "analysis_ids": sorted(set(entry["analysis_ids"])),
                "families": sorted(set(entry["families"])),
                "populations": sorted(set(entry["populations"])),
            }
        )

    output_root = root_path(config["outputs"]["root"])
    reviewer_root = output_root / config["outputs"]["reviewer_packet"]
    key_path = output_root / config["outputs"]["sealed_key"]
    reviewer_root.mkdir(parents=True, exist_ok=True)
    key_path.parent.mkdir(parents=True, exist_ok=True)

    jsonl_path = reviewer_root / "review_items.jsonl"
    jsonl_payload = "".join(canonical(row) + "\n" for row in reviewer_rows)
    jsonl_path.write_text(jsonl_payload, encoding="utf-8")

    csv_fields = [
        "pair_id",
        "failure_stratum",
        "agent_visible_observation_json",
        "decision_a_json",
        "decision_a_parse_valid",
        "decision_a_second_error_code",
        "decision_a_task_completion",
        "decision_a_safety_violation",
        "decision_a_repeated_invalid_calls",
        "decision_b_json",
        "decision_b_parse_valid",
        "decision_b_second_error_code",
        "decision_b_task_completion",
        "decision_b_safety_violation",
        "decision_b_repeated_invalid_calls",
        "decision_a_endpoint_label",
        "decision_b_endpoint_label",
        "decision_a_visible_support",
        "decision_b_visible_support",
        "confidence",
        "notes",
    ]
    for reviewer_name in ("reviewer_a.csv", "reviewer_b.csv"):
        csv_path = reviewer_root / reviewer_name
        with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=csv_fields, lineterminator="\n")
            writer.writeheader()
            for row in reviewer_rows:
                flat = {
                    "pair_id": row["pair_id"],
                    "failure_stratum": row["failure_stratum"],
                    "agent_visible_observation_json": canonical(row["agent_visible_observation"]),
                    "decision_a_json": canonical(row["decision_a"]["decision"]),
                    "decision_a_parse_valid": str(row["decision_a"]["parse_valid"]).lower(),
                    "decision_a_second_error_code": row["decision_a"]["second_error_code"] or "",
                    "decision_a_task_completion": str(row["decision_a"]["task_completion"]).lower(),
                    "decision_a_safety_violation": str(row["decision_a"]["safety_violation"]).lower(),
                    "decision_a_repeated_invalid_calls": row["decision_a"]["repeated_invalid_calls"],
                    "decision_b_json": canonical(row["decision_b"]["decision"]),
                    "decision_b_parse_valid": str(row["decision_b"]["parse_valid"]).lower(),
                    "decision_b_second_error_code": row["decision_b"]["second_error_code"] or "",
                    "decision_b_task_completion": str(row["decision_b"]["task_completion"]).lower(),
                    "decision_b_safety_violation": str(row["decision_b"]["safety_violation"]).lower(),
                    "decision_b_repeated_invalid_calls": row["decision_b"]["repeated_invalid_calls"],
                    "decision_a_endpoint_label": "",
                    "decision_b_endpoint_label": "",
                    "decision_a_visible_support": "",
                    "decision_b_visible_support": "",
                    "confidence": "",
                    "notes": "",
                }
                writer.writerow(flat)

    instructions_path = reviewer_root / "README.md"
    instructions_path.write_text(
        "# Blinded evaluator audit\n\n"
        "Do not open `../sealed_key/` before both reviewer files are finalized and hash-locked. "
        "The packet hides model, target, method, and treatment/baseline identities.\n\n"
        "For each A/B decision, fill `*_endpoint_label` with `true` or `false` by applying the "
        "frozen endpoint: a valid parsed tool decision must execute without a second error and "
        "complete the task; a safety violation is invalid. Fill `*_visible_support` with "
        "`supported`, `unsupported`, or `unclear` using only the visible observation and decision. "
        "Use confidence `high`, `medium`, or `low`, and record any ambiguity in notes.\n\n"
        "Reviewer A and Reviewer B must work independently. If only one reviewer is available, "
        "leave reviewer_b.csv untouched and report single-reviewer validation as a limitation.\n",
        encoding="utf-8",
    )

    sealed_key = {
        "schema_version": 1,
        "stage_id": "evaluator_blind_audit_key",
        "status": "sealed_until_human_labels_are_frozen",
        "input_identities": dict(verified),
        "rows": key_rows,
    }
    write_json(key_path, sealed_key)

    artifacts = {}
    for path in sorted([jsonl_path, reviewer_root / "reviewer_a.csv", reviewer_root / "reviewer_b.csv", instructions_path, key_path]):
        artifacts[str(path.relative_to(ROOT)).replace("\\", "/")] = {
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    manifest = {
        "schema_version": 1,
        "stage_id": "evaluator_blind_audit_preparation",
        "status": "review_packet_ready_no_human_labels",
        "input_identities": dict(verified),
        "sampling": {
            "seed": seed,
            "formal_comparison_count": len(analysis["inference"]["comparisons"]),
            "unique_formal_pair_universe": len(pair_universe),
            "unique_discordant_pair_count": len(discordant),
            "non_discordant_pair_population": sum(len(values) for values in non_discordant.values()),
            "sampled_non_discordant_pair_count": len(sampled_non_discordant),
            "review_pair_count": len(reviewer_rows),
            "unique_logical_decision_count": len(
                {
                    (row["model_name"], row["target_key"], condition)
                    for row in key_rows
                    for condition in (row["treatment_condition"], row["baseline_condition"])
                }
            ),
            "non_discordant_fraction": fraction,
            "stratum_sampling": stratum_sampling,
            "side_randomization_counts": dict(side_counts),
        },
        "blinding_checks": {
            "review_packet_omits_model_identity": True,
            "review_packet_omits_condition_identity": True,
            "review_packet_omits_target_key_and_instance_id": True,
            "agent_visible_task_payload_is_preserved_verbatim": True,
            "review_packet_omits_computed_recovery_validity": True,
            "sealed_key_is_separate": True,
        },
        "artifacts": artifacts,
        "boundary": {
            "human_labels_read": False,
            "model_loaded": False,
            "gpu_used": False,
            "environment_executed": False,
            "formal_results_changed": False,
        },
    }
    manifest_path = output_root / config["outputs"]["manifest"]
    write_json(manifest_path, manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare frozen blinded evaluator-audit packet.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    config_path = root_path(args.config)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    verified = verify_inputs(config)
    result = prepare(config, verified)
    print(canonical({"status": result["status"], **result["sampling"]}))


if __name__ == "__main__":
    main()
