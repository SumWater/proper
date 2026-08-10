from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

import yaml


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs" / "paper_2026" / "e1_finalize_v1_0.yaml"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def root_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def verify_declared_files(entries: Mapping[str, Mapping[str, str]]) -> dict[str, str]:
    verified: dict[str, str] = {}
    for name, entry in entries.items():
        path = root_path(entry["path"])
        actual = sha256_file(path)
        if actual != str(entry["sha256"]):
            raise RuntimeError(f"frozen E1 input hash mismatch: {name}")
        verified[str(name)] = actual
    return verified


def main_payload(config_path: Path) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if config.get("status") != "frozen_before_e1_finalization_outputs":
        raise RuntimeError("E1 finalization config is not frozen")
    runner_hash = sha256_file(Path(__file__).resolve())
    if runner_hash != str(config["runner"]["sha256"]):
        raise RuntimeError("E1 finalizer hash differs from frozen config")
    verified = verify_declared_files(config["inputs"])

    loaded = {
        name: (
            [json.loads(line) for line in root_path(entry["path"]).read_text(encoding="utf-8").splitlines() if line.strip()]
            if str(entry["path"]).endswith(".jsonl")
            else json.loads(root_path(entry["path"]).read_text(encoding="utf-8"))
        )
        for name, entry in config["inputs"].items()
        if str(entry["path"]).endswith((".json", ".jsonl"))
    }
    dense = loaded["dense_result"]
    judge = loaded["judge_result"]
    checkpoint = loaded["judge_checkpoint"]
    deterministic = loaded["deterministic_selections"]
    oracle = loaded["oracle_private"]
    observable = loaded["observable_inputs"]
    if not dense.get("selection_passed") or not judge.get("selection_passed"):
        raise RuntimeError("Dense or Judge result is not passed")
    if judge["records"] != checkpoint:
        raise RuntimeError("Judge final result differs from checkpoint")

    dense_by = {record["target_key"]: record for record in dense["records"]}
    judge_by = {record["target_key"]: record for record in judge["records"]}
    deterministic_by = {
        record["target_key"]: record for record in deterministic["records"]
    }
    oracle_by = {record["target_key"]: record for record in oracle["records"]}
    observable_by = {record["target_key"]: record for record in observable["targets"]}
    target_keys = [record["target_key"] for record in deterministic["records"]]
    if not all(
        set(mapping) == set(target_keys)
        for mapping in (dense_by, judge_by, oracle_by, observable_by)
    ):
        raise RuntimeError("E1 method target-key populations differ")

    methods = (
        "tfidf",
        "dense",
        "llm_judge",
        "proper",
        "proper_no_gate",
        "proper_no_contradiction",
        "oracle",
    )

    def selected(method: str, key: str) -> str | None:
        record = deterministic_by[key]
        if method == "tfidf":
            return record["tfidf"]["selected_memory_key"]
        if method == "dense":
            return dense_by[key]["selected_memory_key"]
        if method == "llm_judge":
            return judge_by[key]["selected_memory_key"]
        if method in {"proper", "proper_no_gate", "proper_no_contradiction"}:
            return record["proper_variants"][method]["selected_memory_key"]
        if method == "oracle":
            return oracle_by[key]["selected_memory_key"]
        raise KeyError(method)

    changed_methods = methods[1:-1]
    changed_sets: dict[str, set[str]] = {method: set() for method in changed_methods}
    applicability = {method: 0 for method in methods}
    corrections = {method: 0 for method in changed_methods}
    new_errors = {method: 0 for method in changed_methods}
    by_stratum: dict[str, dict[str, list[int]]] = {
        method: defaultdict(lambda: [0, 0]) for method in methods
    }
    selection_counts = {method: Counter() for method in methods}
    selection_records: list[dict[str, Any]] = []
    for key in target_keys:
        deterministic_record = deterministic_by[key]
        tfidf_key = selected("tfidf", key)
        oracle_applicability = {
            item["memory_key"]: bool(item["applicable"])
            for item in oracle_by[key]["ranked_applicability"]
        }
        tfidf_applicable = oracle_applicability[str(tfidf_key)]
        selections: dict[str, Any] = {}
        for method in methods:
            memory_key = selected(method, key)
            is_applicable = (
                memory_key is not None
                if method == "oracle"
                else oracle_applicability[str(memory_key)]
            )
            selections[method] = {
                "selected_memory_key": memory_key,
                "applicable": is_applicable,
            }
            if memory_key is not None:
                selection_counts[method][str(memory_key)] += 1
            applicability[method] += int(is_applicable)
            stratum = str(deterministic_record["stratum"])
            by_stratum[method][stratum][0] += int(is_applicable)
            by_stratum[method][stratum][1] += 1
            if method in changed_methods:
                if memory_key != tfidf_key:
                    changed_sets[method].add(key)
                corrections[method] += int((not tfidf_applicable) and is_applicable)
                new_errors[method] += int(tfidf_applicable and (not is_applicable))
        union_member = any(key in changed_sets[method] for method in changed_methods)
        selection_records.append(
            {
                "target_key": key,
                "stratum": deterministic_record["stratum"],
                "instance_id": deterministic_record["instance_id"],
                "prefix_sha256": deterministic_record["prefix_sha256"],
                "selections": selections,
                "changed_from_tfidf": {
                    method: key in changed_sets[method] for method in changed_methods
                },
                "changed_target_union_member": union_member,
            }
        )

    union = set().union(*changed_sets.values())
    if len(union) != int(config["expected"]["changed_target_union_count"]):
        raise RuntimeError("changed-target union differs from frozen expected count")
    for record in selection_records:
        key = record["target_key"]
        record["changed_target_union_member"] = key in union

    prompt_manifest = {
        "schema_version": 1,
        "stage_id": "e1_selection",
        "model": "Qwen3-8B",
        "model_manifest_sha256": config["prompt_identity"]["model_manifest_sha256"],
        "prompt_version": config["prompt_identity"]["prompt_version"],
        "prompt_source_sha256": config["prompt_identity"]["prompt_source_sha256"],
        "generation": config["prompt_identity"]["generation"],
        "records": [
            {
                "target_key": record["target_key"],
                "rendered_prompt_sha256": record["rendered_prompt_sha256"],
                "prompt_tokens": record["prompt_tokens"],
                "completion_tokens": record["completion_tokens"],
            }
            for record in judge["records"]
        ],
    }
    prompt_positions = Counter(
        record["selected_candidate_id"] for record in judge["records"]
    )
    overlaps = {
        f"{left}_and_{right}": len(changed_sets[left] & changed_sets[right])
        for index, left in enumerate(changed_methods)
        for right in changed_methods[index + 1 :]
    }
    unique_prompt_counts: dict[str, int] = {}
    for key in target_keys:
        memory_keys = {selected(method, key) for method in methods}
        memory_keys.discard(None)
        unique_prompt_counts[key] = 1 + len(memory_keys)
    union_unique_per_model = sum(unique_prompt_counts[key] for key in union)
    all_unique_per_model = sum(unique_prompt_counts.values())
    analysis = {
        "schema_version": 1,
        "stage_id": "e1_selection",
        "target_count": len(target_keys),
        "changed_counts": {
            method: len(values) for method, values in changed_sets.items()
        },
        "changed_by_stratum": {
            method: {
                stratum: sum(
                    1
                    for key in values
                    if deterministic_by[key]["stratum"] == stratum
                )
                for stratum in sorted(
                    {record["stratum"] for record in deterministic["records"]}
                )
            }
            for method, values in changed_sets.items()
        },
        "changed_target_union_count": len(union),
        "changed_target_union_by_stratum": {
            stratum: sum(
                1 for key in union if deterministic_by[key]["stratum"] == stratum
            )
            for stratum in sorted(
                {record["stratum"] for record in deterministic["records"]}
            )
        },
        "changed_set_overlaps": overlaps,
        "applicable_selection_counts": applicability,
        "applicable_selection_by_stratum": {
            method: {
                stratum: {"applicable": counts[0], "total": counts[1]}
                for stratum, counts in sorted(values.items())
            }
            for method, values in by_stratum.items()
        },
        "corrections_vs_tfidf": corrections,
        "new_errors_vs_tfidf": new_errors,
        "judge_candidate_position_counts": dict(sorted(prompt_positions.items())),
        "selection_concentration": {
            method: {
                "unique_selected_memories": len(counts),
                "maximum_single_memory_count": max(counts.values()),
                "maximum_single_memory_share": max(counts.values()) / len(target_keys),
            }
            for method, counts in selection_counts.items()
        },
        "planned_agent_workload_before_historical_cache_join": {
            "agent_models": 2,
            "logical_conditions": 8,
            "logical_condition_rows_all_targets": len(target_keys) * 8 * 2,
            "unique_prompts_per_model_all_targets": all_unique_per_model,
            "unique_prompts_two_models_all_targets": all_unique_per_model * 2,
            "unique_prompts_per_model_union_only": union_unique_per_model,
            "unique_prompts_two_models_union_only": union_unique_per_model * 2,
            "historical_qwen_cache_join_pending": True,
        },
    }
    result = {
        "schema_version": 1,
        "status": "completed",
        "stage_id": "e1_selection",
        "counts": {
            "targets": len(target_keys),
            "memories": len(observable["memories"]),
            "changed_target_union": len(union),
            "outside_union": len(target_keys) - len(union),
            "judge_parse_fallbacks": judge["counts"]["fallbacks"],
        },
        "selection_applicability": applicability,
        "authorization": {
            "e1_selection_complete": True,
            "formal_agent_generation": False,
            "next_gate": "freeze_agent_prompt_serializer_and_historical_qwen_cache_join",
        },
    }
    selection_manifest = {
        "schema_version": 1,
        "status": "frozen",
        "stage_id": "e1_selection",
        "union_definition": list(changed_methods),
        "union_count": len(union),
        "records": selection_records,
    }
    source_lines = []
    source_entries = {
        **config["inputs"],
        "finalization_config": {
            "path": str(config_path.relative_to(ROOT)).replace("\\", "/"),
            "sha256": sha256_file(config_path),
        },
        "finalizer": config["runner"],
    }
    for name in sorted(source_entries):
        entry = source_entries[name]
        source_lines.append(f"{entry['sha256']}  {entry['path']}")
    return (
        {
            "selection_manifest": selection_manifest,
            "prompt_manifest": prompt_manifest,
            "results": result,
            "analysis": analysis,
            "exclusions": {
                "schema_version": 1,
                "stage_id": "e1_selection",
                "excluded_targets": [],
                "count": 0,
            },
        },
        config,
        source_lines,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify and freeze complete E1 selections.")
    parser.add_argument("--config", type=Path, default=CONFIG)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = args.config.resolve()
    payloads, config, source_lines = main_payload(config_path)
    outputs = config["outputs"]
    for name in ("selection_manifest", "prompt_manifest", "results", "analysis", "exclusions"):
        write_json(root_path(outputs[name]), payloads[name])
    root_path(outputs["source_manifest"]).write_text(
        "\n".join(source_lines) + "\n", encoding="utf-8"
    )
    protocol = """# E1 offline selection protocol\n\nStatus: completed and frozen under paper protocol `1.0-frozen`.\n\nThe changed-target union contains targets where Dense, LLM Judge, PROPER,\nPROPER-no-gate, or PROPER-no-contradiction differs from TF-IDF Rank-1.\nNo Memory and Oracle do not define the union. Evaluator applicability labels\nwere read only after all non-oracle selections were frozen. No agent action\nwas generated in E1.\n"""
    root_path(outputs["protocol"]).write_text(protocol, encoding="utf-8")
    reproduction = """# Reproduce E1 selection finalization\n\nFrom the repository root:\n\n```bash\npython experiments/paper_2026/finalize_e1_selection.py \\\n  --config configs/paper_2026/e1_finalize_v1_0.yaml\n```\n\nThe command verifies all frozen source hashes before overwriting E1 summary\nartifacts. It does not load a model or generate an agent action.\n"""
    root_path(outputs["reproduction"]).write_text(reproduction, encoding="utf-8")
    print(json.dumps(payloads["results"], indent=2, sort_keys=True))
    print(f"OUTPUT={root_path(outputs['selection_manifest'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
