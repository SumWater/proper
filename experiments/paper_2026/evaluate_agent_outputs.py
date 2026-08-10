from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

import yaml


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs" / "paper_2026" / "agent_evaluation_v1_0.yaml"
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "src"),
    str(ROOT / "external" / "toolmisusebench"),
    str(ROOT / "experiments" / "proper_v1"),
    str(ROOT / "experiments" / "proper_v2"),
    str(ROOT / "experiments" / "paper_2026"),
]

import selector_capacity_audit as capacity  # noqa: E402
from agent_runtime import (  # noqa: E402
    decision_payload,
    execute_condition,
    parse_decision,
)
from confirmatory_gate_v1 import verify_test_file  # noqa: E402
from toolmisusebench.dataset import load_tasks  # noqa: E402


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


def verify_inputs(config: Mapping[str, Any]) -> dict[str, str]:
    if config.get("status") != "frozen_before_per_target_environment_evaluation":
        raise RuntimeError("agent-evaluation config is not frozen")
    if sha256_file(Path(__file__).resolve()) != config["runner"]["sha256"]:
        raise RuntimeError("agent-evaluation runner differs from frozen config")
    verified: dict[str, str] = {}
    for name, entry in config["inputs"].items():
        path = root_path(entry["path"])
        if not path.is_file():
            raise RuntimeError(f"missing frozen evaluator input: {name}: {path}")
        actual = sha256_file(path)
        if actual != entry["sha256"]:
            raise RuntimeError(f"frozen evaluator input hash mismatch: {name}: {actual}")
        verified[name] = actual
    manifest = root_path(config["inputs"]["p0_source_manifest"]["path"])
    checked = 0
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, separator, relative = line.partition("  ")
        relative_path = Path(relative)
        if not separator or relative_path.is_absolute() or ".." in relative_path.parts:
            raise RuntimeError(f"invalid P0 source-manifest row: {line!r}")
        candidate = ROOT / relative_path
        if not candidate.is_file() or sha256_file(candidate) != expected:
            raise RuntimeError(f"P0 source-manifest mismatch: {relative}")
        checked += 1
    if checked != int(config["expected"]["p0_source_manifest_entries"]):
        raise RuntimeError("P0 source-manifest entry count mismatch")
    return verified


def model_outputs(config: Mapping[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    historical = read_json(root_path(config["inputs"]["historical_qwen_cache"]["path"]))
    qwen_new = read_json(root_path(config["inputs"]["qwen_result"]["path"]))
    mistral = read_json(root_path(config["inputs"]["mistral_result"]["path"]))
    if qwen_new["status"] != "complete" or mistral["status"] != "complete":
        raise RuntimeError("formal generation result is incomplete")

    qwen: dict[str, dict[str, Any]] = {}
    for item in historical["records"]:
        result = item["result"]
        prompt_hash = item["prompt_sha256"]
        raw = result["model_output"]
        decision, parse_valid, parse_error = parse_decision(raw)
        if result["decision"] != decision_payload(decision):
            raise RuntimeError(f"historical parsed decision mismatch: {prompt_hash}")
        if result["parse_valid"] != parse_valid or result["parse_error"] != parse_error:
            raise RuntimeError(f"historical parse metadata mismatch: {prompt_hash}")
        qwen[prompt_hash] = {
            "raw_model_output": raw,
            "raw_model_output_sha256": result["model_output_sha256"],
            "decision": result["decision"],
            "parse_valid": parse_valid,
            "parse_error": parse_error,
            "provenance": "historical_exact_model_output_cache",
        }
    for item in qwen_new["records"]:
        prompt_hash = item["prompt_sha256"]
        if prompt_hash in qwen:
            raise RuntimeError(f"new Qwen output overlaps historical cache: {prompt_hash}")
        qwen[prompt_hash] = {
            "raw_model_output": item["raw_model_output"],
            "raw_model_output_sha256": item["raw_model_output_sha256"],
            "decision": item["decision"],
            "parse_valid": item["parse_valid"],
            "parse_error": item["parse_error"],
            "provenance": "new_formal_generation",
        }
    mistral_by = {
        item["prompt_sha256"]: {
            "raw_model_output": item["raw_model_output"],
            "raw_model_output_sha256": item["raw_model_output_sha256"],
            "decision": item["decision"],
            "parse_valid": item["parse_valid"],
            "parse_error": item["parse_error"],
            "provenance": "new_formal_generation",
        }
        for item in mistral["records"]
    }
    expected = int(config["expected"]["unique_prompts_per_model"])
    if len(qwen) != expected or len(mistral_by) != expected:
        raise RuntimeError("complete model-output prompt coverage was not reconstructed")
    if set(qwen) != set(mistral_by):
        raise RuntimeError("Qwen and Mistral prompt populations differ")
    return {"qwen3_8b": qwen, "mistral_7b_instruct_v0_3": mistral_by}


def reconstruct_instances(config: Mapping[str, Any]) -> dict[str, Any]:
    capacity_config = capacity.load_config(
        root_path(config["inputs"]["selector_capacity_config"]["path"])
    )
    formal_config = yaml.safe_load(capacity.FORMAL_RUNTIME_CONFIG.read_text(encoding="utf-8"))
    public_test = verify_test_file(formal_config)
    tasks = load_tasks(public_test.parent, str(formal_config["dataset"]["split"]))
    task_by_id = {task.task_id: task for task in tasks}
    cohorts = capacity.load_cohort_records(capacity_config)
    instances: dict[str, Any] = {}
    for stratum, records in cohorts.items():
        for record in records:
            task = task_by_id.get(record["source_task_id"])
            if task is None:
                raise RuntimeError(f"frozen target task is absent: {record['source_task_id']}")
            instance = capacity.build_instance(stratum, task)
            if instance is None or instance.instance_id != record["instance_id"]:
                raise RuntimeError(f"target instance reconstruction mismatch: {record['instance_id']}")
            if instance.instance_id in instances:
                raise RuntimeError(f"duplicate target instance identity: {instance.instance_id}")
            instances[instance.instance_id] = instance
    if len(instances) != int(config["expected"]["target_count"]):
        raise RuntimeError("reconstructed target count mismatch")
    return instances


def outcome_payload(outcome: Any) -> dict[str, Any]:
    return {
        "recovery_validity": outcome.recovery_validity,
        "task_completion": outcome.task_completion,
        "safety_violation": outcome.safety_violation,
        "repeated_invalid_calls": outcome.repeated_invalid_calls,
        "recovery_steps": outcome.recovery_steps,
        "recovery_tool_calls": outcome.recovery_tool_calls,
    }


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        populations = ["all_valid_targets"]
        if record["changed_target_union_member"]:
            populations.append("changed_target_union")
        for population in populations:
            grouped[(record["model_name"], record["condition"], record["stratum"], population)].append(record)
    rows = []
    for (model, condition, stratum, population), values in sorted(grouped.items()):
        rows.append(
            {
                "model_name": model,
                "condition": condition,
                "stratum": stratum,
                "population": population,
                "n": len(values),
                "recovery_validity_count": sum(item["outcome"]["recovery_validity"] for item in values),
                "task_completion_count": sum(item["outcome"]["task_completion"] for item in values),
                "safety_violation_count": sum(item["outcome"]["safety_violation"] for item in values),
                "repeated_invalid_calls_count": sum(item["outcome"]["repeated_invalid_calls"] for item in values),
                "parse_failure_count": sum(not item["parse_valid"] for item in values),
                "recovery_tool_calls": sum(item["outcome"]["recovery_tool_calls"] for item in values),
            }
        )
    return {"rows": rows, "row_count": len(rows)}


def evaluate(config: Mapping[str, Any], verified: Mapping[str, str]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    prompt_manifest = read_json(root_path(config["inputs"]["prompt_manifest"]["path"]))
    selection_manifest = read_json(root_path(config["inputs"]["selection_manifest"]["path"]))
    outputs = model_outputs(config)
    instances = reconstruct_instances(config)
    selection_by_target = {item["target_key"]: item for item in selection_manifest["records"]}
    conditions = tuple(prompt_manifest["conditions"])
    if conditions != tuple(config["conditions"]):
        raise RuntimeError("prompt condition order differs from frozen evaluator config")

    records: list[dict[str, Any]] = []
    provenance_counts: Counter[str] = Counter()
    for model_name in config["models"]:
        for target in prompt_manifest["target_records"]:
            instance = instances.get(target["instance_id"])
            if instance is None:
                raise RuntimeError(f"target instance absent: {target['instance_id']}")
            selection = selection_by_target[target["target_key"]]
            if selection["prefix_sha256"] != target["prefix_sha256"]:
                raise RuntimeError("selection/prompt prefix mismatch")
            for condition in conditions:
                identity = target["conditions"][condition]
                output = outputs[model_name].get(identity["prompt_sha256"])
                if output is None:
                    raise RuntimeError("model output absent for target-condition prompt")
                decision, parse_valid, parse_error = parse_decision(output["raw_model_output"])
                if output["decision"] != decision_payload(decision):
                    raise RuntimeError("saved and reparsed model decisions differ")
                if output["parse_valid"] != parse_valid or output["parse_error"] != parse_error:
                    raise RuntimeError("saved and reparsed parse metadata differ")
                outcome, trace = execute_condition(instance, decision)
                if trace["prefix_hash"] != target["prefix_sha256"]:
                    raise RuntimeError("evaluation environment prefix differs from frozen prompt")
                provenance_counts[output["provenance"]] += 1
                records.append(
                    {
                        "model_name": model_name,
                        "target_key": target["target_key"],
                        "instance_id": target["instance_id"],
                        "prefix_sha256": target["prefix_sha256"],
                        "stratum": target["stratum"],
                        "changed_target_union_member": target["changed_target_union_member"],
                        "condition": condition,
                        "selected_memory_key": identity["memory_key"],
                        "selection_applicable": (
                            None
                            if condition == "no_memory"
                            else selection["selections"][condition]["applicable"]
                        ),
                        "prompt_sha256": identity["prompt_sha256"],
                        "messages_sha256": identity["messages_sha256"],
                        "model_output_provenance": output["provenance"],
                        "raw_model_output_sha256": output["raw_model_output_sha256"],
                        "decision": output["decision"],
                        "parse_valid": parse_valid,
                        "parse_error": parse_error,
                        "outcome": outcome_payload(outcome),
                        "second_error_code": trace["second_error_code"],
                        "trace_sha256": trace["trace_sha256"],
                    }
                )
    expected_rows = int(config["expected"]["logical_rows_two_models"])
    if len(records) != expected_rows:
        raise RuntimeError("evaluated logical-row count mismatch")
    analysis = {
        "schema_version": 1,
        "stage_id": "e2_e3_agent_evaluation",
        "status": "preliminary_counts_no_formal_inference_tests_yet",
        "summary": summarize(records),
    }
    result = {
        "schema_version": 1,
        "stage_id": "e2_e3_agent_evaluation",
        "status": "complete",
        "input_identities": dict(verified),
        "record_count": len(records),
        "models": list(config["models"]),
        "conditions": list(conditions),
        "model_output_provenance_logical_rows": dict(sorted(provenance_counts.items())),
        "records": records,
    }
    audit = {
        "schema_version": 1,
        "stage_id": "e2_e3_agent_evaluation",
        "status": "passed",
        "checks": {
            "all_frozen_input_hashes": True,
            "p0_source_manifest_verified": True,
            "complete_two_model_prompt_coverage": True,
            "historical_qwen_model_output_only_reuse": True,
            "every_target_condition_environment_evaluated_separately": True,
            "all_environment_prefixes_match_frozen_prompts": True,
            "all_decisions_reparsed_with_frozen_parser": True,
            "selective_regeneration_or_parse_repair": False,
        },
        "counts": {
            "target_count": int(config["expected"]["target_count"]),
            "model_count": len(config["models"]),
            "condition_count": len(conditions),
            "logical_rows": len(records),
            "preliminary_summary_rows": analysis["summary"]["row_count"],
        },
    }
    return result, analysis, audit


def main() -> None:
    parser = argparse.ArgumentParser(description="Frozen per-target E2/E3 environment evaluator.")
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()
    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    verified = verify_inputs(config)
    result, analysis, audit = evaluate(config, verified)
    write_json(root_path(config["outputs"]["results"]), result)
    write_json(root_path(config["outputs"]["analysis_preliminary"]), analysis)
    write_json(root_path(config["outputs"]["audit"]), audit)
    print(json.dumps(audit["counts"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
