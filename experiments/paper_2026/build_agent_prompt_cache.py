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
CONFIG = ROOT / "configs" / "paper_2026" / "agent_prompt_cache_v1_0.yaml"
sys.path.insert(0, str(ROOT))

from experiments.proper_v1.agent_runtime import (  # noqa: E402
    agent_messages,
    build_prompt,
    canonical,
    sha256_text,
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


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def verify_inputs(entries: Mapping[str, Mapping[str, str]]) -> dict[str, str]:
    verified: dict[str, str] = {}
    for name, entry in entries.items():
        path = root_path(entry["path"])
        if not path.is_file():
            raise RuntimeError(f"missing frozen input: {name}: {path}")
        actual = sha256_file(path)
        if actual != str(entry["sha256"]):
            raise RuntimeError(f"frozen input hash mismatch: {name}: {actual}")
        verified[str(name)] = actual
    return verified


def visible_observation(context: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "instruction": context["user_instruction"],
        "tool_schemas": context["public_tool_schemas"],
        "transcript": context["observable_history"],
        "remaining_budget": context["remaining_retry_budget"],
        "last_error": context["public_error_or_return"]["error"],
    }


def historical_core(condition: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: condition.get(key)
        for key in (
            "prompt",
            "prompt_sha256",
            "prefix_hash",
            "model_output",
            "model_output_sha256",
            "decision",
            "parse_valid",
            "parse_error",
        )
    }


def build_payloads(config_path: Path) -> tuple[dict[str, Any], ...]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if config.get("status") != "frozen_before_agent_prompt_cache_outputs":
        raise RuntimeError("agent prompt-cache config is not frozen")
    if sha256_file(Path(__file__).resolve()) != str(config["runner"]["sha256"]):
        raise RuntimeError("prompt-cache runner hash differs from frozen config")
    verified = verify_inputs(config["inputs"])

    selection = read_json(root_path(config["inputs"]["selection_manifest"]["path"]))
    observable = read_json(root_path(config["inputs"]["observable_inputs"]["path"]))
    expected = config["expected"]
    methods = tuple(config["conditions"]["memory_conditions"])
    conditions = (str(config["conditions"]["no_memory"]),) + methods

    if len(selection["records"]) != int(expected["target_count"]):
        raise RuntimeError("selection target count differs from frozen expectation")
    if tuple(sorted(selection["records"], key=lambda item: item["target_key"])) != tuple(
        selection["records"]
    ):
        raise RuntimeError("selection records are not deterministically target-key ordered")

    targets = {item["target_key"]: item for item in observable["targets"]}
    memories = {item["memory_key"]: item for item in observable["memories"]}
    if len(targets) != int(expected["target_count"]):
        raise RuntimeError("observable target population differs from frozen expectation")
    if len(memories) != int(expected["memory_count"]):
        raise RuntimeError("memory population differs from frozen expectation")
    for key, item in memories.items():
        if sha256_text(item["natural_text"]) != item["natural_text_sha256"]:
            raise RuntimeError(f"memory natural-text hash mismatch: {key}")

    prompt_index: dict[str, dict[str, Any]] = {}
    prompt_records: list[dict[str, Any]] = []
    logical_rows = 0
    target_unique_prompt_sum = 0
    union_hashes: set[str] = set()
    prefix_checks = 0
    for record in selection["records"]:
        target_key = record["target_key"]
        source = targets.get(target_key)
        if source is None:
            raise RuntimeError(f"selection target absent from observable inputs: {target_key}")
        visible = visible_observation(source["judge_context"])
        prefix_sha256 = sha256_text(canonical(visible))
        if prefix_sha256 != record["prefix_sha256"]:
            raise RuntimeError(f"reconstructed prefix hash mismatch: {target_key}")
        prefix_checks += 1
        condition_map: dict[str, Any] = {}
        for condition in conditions:
            memory_key = None
            memory_text = None
            if condition != config["conditions"]["no_memory"]:
                selected = record["selections"].get(condition)
                if selected is None:
                    raise RuntimeError(f"selection missing condition: {target_key}: {condition}")
                memory_key = selected["selected_memory_key"]
                if memory_key not in memories:
                    raise RuntimeError(f"unknown selected memory: {target_key}: {memory_key}")
                memory_text = memories[memory_key]["natural_text"]
            prompt = build_prompt(visible, memory_text)
            prompt_hash = sha256_text(prompt)
            messages = agent_messages(prompt)
            messages_hash = sha256_text(canonical(messages))
            condition_map[condition] = {
                "memory_key": memory_key,
                "prompt_sha256": prompt_hash,
                "messages_sha256": messages_hash,
            }
            logical_rows += 1
            if record["changed_target_union_member"]:
                union_hashes.add(prompt_hash)
            proposed = {
                "prompt_sha256": prompt_hash,
                "messages_sha256": messages_hash,
                "prompt": prompt,
                "messages": messages,
                "prefix_sha256": prefix_sha256,
                "union_member": bool(record["changed_target_union_member"]),
                "target_keys": [target_key],
                "instance_ids": [record["instance_id"]],
                "strata": [record["stratum"]],
                "memory_keys": [memory_key],
                "conditions": [condition],
                "occurrences": [
                    {
                        "target_key": target_key,
                        "instance_id": record["instance_id"],
                        "stratum": record["stratum"],
                        "union_member": bool(record["changed_target_union_member"]),
                        "memory_key": memory_key,
                        "condition": condition,
                    }
                ],
            }
            existing = prompt_index.get(prompt_hash)
            if existing is None:
                prompt_index[prompt_hash] = proposed
            else:
                immutable_keys = (
                    "prompt_sha256",
                    "messages_sha256",
                    "prompt",
                    "messages",
                    "prefix_sha256",
                )
                if any(existing[key] != proposed[key] for key in immutable_keys):
                    raise RuntimeError(f"prompt SHA-256 collision or inconsistent identity: {prompt_hash}")
                existing["union_member"] = existing["union_member"] or proposed["union_member"]
                for aggregate, value in (
                    ("target_keys", target_key),
                    ("instance_ids", record["instance_id"]),
                    ("strata", record["stratum"]),
                    ("memory_keys", memory_key),
                    ("conditions", condition),
                ):
                    if value not in existing[aggregate]:
                        existing[aggregate].append(value)
                existing["occurrences"].extend(proposed["occurrences"])
        prompt_records.append(
            {
                "target_key": target_key,
                "instance_id": record["instance_id"],
                "prefix_sha256": prefix_sha256,
                "stratum": record["stratum"],
                "changed_target_union_member": bool(record["changed_target_union_member"]),
                "conditions": condition_map,
            }
        )
        target_unique_prompt_sum += len(
            {item["prompt_sha256"] for item in condition_map.values()}
        )

    if logical_rows != int(expected["logical_prompt_rows_per_model"]):
        raise RuntimeError("logical prompt-row count differs from frozen expectation")
    if target_unique_prompt_sum != int(expected["target_deduplicated_prompts_per_model"]):
        raise RuntimeError("target-deduplicated prompt count differs from frozen expectation")
    if len(prompt_index) != int(expected["unique_prompts_per_model"]):
        raise RuntimeError("unique prompt count differs from frozen expectation")
    if len(union_hashes) != int(expected["union_unique_prompts_per_model"]):
        raise RuntimeError("union-only unique prompt count differs from frozen expectation")

    historical: dict[str, dict[str, Any]] = {}
    source_summaries: list[dict[str, Any]] = []
    historical_occurrences = 0
    expected_model = str(config["identity"]["qwen_model_manifest_sha256"])
    expected_conda = str(config["identity"]["conda_explicit_sha256"])
    for source_name in config["historical_sources"]:
        entry = config["inputs"][source_name]
        payload = read_json(root_path(entry["path"]))
        identities = payload.get("identities", {})
        if identities.get("model_manifest_sha256") != expected_model:
            raise RuntimeError(f"historical model identity mismatch: {source_name}")
        if identities.get("conda_explicit_lock_sha256") != expected_conda:
            raise RuntimeError(f"historical conda identity mismatch: {source_name}")
        if int(payload.get("model_output_parse_failure_count", 0)) != 0:
            raise RuntimeError(f"historical source contains model parse failures: {source_name}")
        source_conditions: Counter[str] = Counter()
        for record in payload["records"]:
            for condition_name, condition in record["conditions"].items():
                historical_occurrences += 1
                source_conditions[condition_name] += 1
                prompt = condition["prompt"]
                prompt_hash = sha256_text(prompt)
                if prompt_hash != condition["prompt_sha256"]:
                    raise RuntimeError(f"historical raw prompt hash mismatch: {source_name}")
                if prompt_hash != record["prompt_sha256"][condition_name]:
                    raise RuntimeError(f"historical record prompt map mismatch: {source_name}")
                if condition.get("prefix_hash") != record["prefix_sha256"]:
                    raise RuntimeError(f"historical prefix mismatch: {source_name}")
                if sha256_text(condition["model_output"]) != condition["model_output_sha256"]:
                    raise RuntimeError(f"historical model-output hash mismatch: {source_name}")
                core = historical_core(condition)
                occurrence = {
                    "source_name": source_name,
                    "source_path": entry["path"],
                    "source_sha256": entry["sha256"],
                    "condition": condition_name,
                    "instance_id": record["instance_id"],
                    "prefix_sha256": record["prefix_sha256"],
                    "reused_from_condition": condition.get("reused_from_condition"),
                    "historical_evaluation": {
                        "outcome": condition.get("outcome"),
                        "second_error_code": condition.get("second_error_code"),
                        "trace_sha256": condition.get("trace_sha256"),
                    },
                }
                if prompt_hash not in historical:
                    historical[prompt_hash] = {
                        "prompt_sha256": prompt_hash,
                        "identity": {
                            "model_manifest_sha256": expected_model,
                            "conda_explicit_sha256": expected_conda,
                            "agent_runtime_sha256": verified["agent_runtime"],
                            "generation": config["identity"]["generation"],
                        },
                        "result": core,
                        "occurrences": [occurrence],
                    }
                else:
                    if historical[prompt_hash]["result"] != core:
                        raise RuntimeError(
                            f"conflicting deterministic historical model output for prompt: {prompt_hash}"
                        )
                    historical[prompt_hash]["occurrences"].append(occurrence)
        source_summaries.append(
            {
                "source_name": source_name,
                "path": entry["path"],
                "sha256": entry["sha256"],
                "record_count": len(payload["records"]),
                "condition_occurrences": dict(sorted(source_conditions.items())),
            }
        )

    join_records: list[dict[str, Any]] = []
    qwen_missing: list[str] = []
    hit_by_stratum: Counter[str] = Counter()
    hit_by_union: Counter[str] = Counter()
    hit_by_condition: Counter[str] = Counter()
    for prompt_hash in sorted(prompt_index):
        planned = prompt_index[prompt_hash]
        cached = historical.get(prompt_hash)
        reusable = False
        provenance: list[dict[str, Any]] = []
        if cached is not None:
            if cached["result"]["prompt"] != planned["prompt"]:
                raise RuntimeError(f"cache join raw-prompt mismatch: {prompt_hash}")
            provenance = [
                item
                for item in cached["occurrences"]
                if item["prefix_sha256"] == planned["prefix_sha256"]
            ]
            reusable = bool(provenance)
        if reusable:
            for stratum in planned["strata"]:
                hit_by_stratum[stratum] += 1
            hit_by_union[str(bool(planned["union_member"])).lower()] += 1
            for occurrence in planned["occurrences"]:
                hit_by_condition[occurrence["condition"]] += 1
        else:
            qwen_missing.append(prompt_hash)
        join_records.append(
            {
                "prompt_sha256": prompt_hash,
                "target_keys": planned["target_keys"],
                "instance_ids": planned["instance_ids"],
                "prefix_sha256": planned["prefix_sha256"],
                "strata": planned["strata"],
                "union_member": planned["union_member"],
                "conditions": planned["conditions"],
                "qwen_cache_status": "reusable_exact_identity" if reusable else "miss",
                "historical_provenance": provenance,
            }
        )

    qwen_hits = len(prompt_index) - len(qwen_missing)
    summary = {
        "target_count": len(prompt_records),
        "condition_count": len(conditions),
        "logical_prompt_rows_per_model": logical_rows,
        "target_deduplicated_prompts_per_model": target_unique_prompt_sum,
        "unique_prompts_per_model": len(prompt_index),
        "union_unique_prompts_per_model": len(union_hashes),
        "historical_condition_occurrences": historical_occurrences,
        "historical_unique_prompts": len(historical),
        "qwen_exact_cache_hits": qwen_hits,
        "qwen_new_calls": len(qwen_missing),
        "mistral_new_calls": len(prompt_index),
        "two_model_new_calls": len(qwen_missing) + len(prompt_index),
        "two_model_logical_rows": logical_rows * 2,
        "prefix_reconstruction_checks": prefix_checks,
        "cache_hits_by_stratum": dict(sorted(hit_by_stratum.items())),
        "cache_hits_by_union_membership": dict(sorted(hit_by_union.items())),
        "cache_condition_references": dict(sorted(hit_by_condition.items())),
    }

    prompt_manifest = {
        "schema_version": 1,
        "stage_id": "agent_prompt_cache",
        "status": "prompt_identities_frozen_no_new_model_outputs",
        "identity": config["identity"],
        "conditions": list(conditions),
        "summary": summary,
        "target_records": prompt_records,
        "unique_prompts": [prompt_index[key] for key in sorted(prompt_index)],
    }
    historical_cache = {
        "schema_version": 1,
        "stage_id": "agent_prompt_cache",
        "status": "conditionally_reusable_exact_identity_cache",
        "source_summaries": source_summaries,
        "summary": {
            "condition_occurrences": historical_occurrences,
            "unique_prompts": len(historical),
            "conflicts": 0,
        },
        "records": [historical[key] for key in sorted(historical)],
    }
    cache_join = {
        "schema_version": 1,
        "stage_id": "agent_prompt_cache",
        "status": "exact_identity_join_passed",
        "summary": summary,
        "records": join_records,
    }
    planned_calls = {
        "schema_version": 1,
        "stage_id": "agent_prompt_cache",
        "status": "planned_not_executed",
        "formal_agent_generation_authorized": False,
        "prompt_manifest_path": config["outputs"]["prompt_manifest"],
        "models": {
            "qwen3_8b": {
                "model_manifest_sha256": expected_model,
                "cache_hit_count": qwen_hits,
                "new_call_count": len(qwen_missing),
                "new_prompt_sha256": qwen_missing,
            },
            "mistral_7b_instruct_v0_3": {
                "model_manifest_sha256": config["identity"]["mistral_model_manifest_sha256"],
                "cache_hit_count": 0,
                "new_call_count": len(prompt_index),
                "new_prompt_sha256": sorted(prompt_index),
            },
        },
        "summary": summary,
    }
    audit = {
        "schema_version": 1,
        "stage_id": "agent_prompt_cache",
        "status": "passed",
        "verified_inputs": verified,
        "checks": {
            "frozen_runner": True,
            "all_input_hashes": True,
            "memory_text_hashes": True,
            "prefix_reconstruction": True,
            "prompt_raw_sha256": True,
            "message_identity_sha256": True,
            "historical_model_identity": True,
            "historical_environment_identity": True,
            "historical_prompt_and_output_hashes": True,
            "historical_duplicate_model_output_consistency": True,
            "historical_outcomes_not_reused_across_instances": True,
            "exact_cache_join_identity": True,
            "new_model_outputs_generated": False,
        },
        "summary": summary,
    }
    return prompt_manifest, historical_cache, cache_join, planned_calls, audit


def write_source_manifest(config: Mapping[str, Any], output_path: Path) -> None:
    paths = [root_path(config["runner"]["path"]), CONFIG]
    paths.extend(root_path(item["path"]) for item in config["inputs"].values())
    lines = [
        f"{sha256_file(path)}  {path.resolve().relative_to(ROOT.resolve()).as_posix()}"
        for path in sorted(set(paths), key=lambda item: item.as_posix())
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()
    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    payloads = build_payloads(config_path)
    output_names = ("prompt_manifest", "historical_cache", "cache_join", "planned_calls", "audit")
    for name, payload in zip(output_names, payloads, strict=True):
        write_json(root_path(config["outputs"][name]), payload)
    write_source_manifest(config, root_path(config["outputs"]["source_manifest"]))
    print(json.dumps(payloads[-1]["summary"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
