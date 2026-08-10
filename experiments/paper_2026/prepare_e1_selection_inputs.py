from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

import yaml


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [
    str(ROOT / "src"),
    str(ROOT / "external" / "toolmisusebench"),
    str(ROOT / "experiments" / "proper_v1"),
    str(ROOT / "experiments" / "proper_v2"),
    str(ROOT / "experiments" / "paper_2026"),
]

import selector_capacity_audit as capacity  # noqa: E402
from agent_runtime import prepare_prefix  # noqa: E402
from confirmatory_gate_v1 import verify_test_file  # noqa: E402
from failure_memory.retrieval import FailureQuery, SourceBlindTfidfRetriever  # noqa: E402
from gate_dataset import as_experience  # noqa: E402
from toolmisusebench.dataset import load_tasks  # noqa: E402


CONFIG = ROOT / "configs" / "paper_2026" / "e1_selection_v1_0.yaml"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    rendered = json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def root_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def verify_source_manifest(path: Path) -> dict[str, Any]:
    checked = 0
    failures: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, separator, relative = line.partition("  ")
        relative_path = Path(relative)
        if (
            not separator
            or len(expected) != 64
            or relative_path.is_absolute()
            or ".." in relative_path.parts
        ):
            failures.append({"entry": line, "reason": "invalid_manifest_entry"})
            continue
        candidate = ROOT / relative_path
        checked += 1
        if not candidate.is_file():
            failures.append({"path": relative, "reason": "missing"})
        elif sha256_file(candidate) != expected:
            failures.append({"path": relative, "reason": "hash_mismatch"})
    return {"checked": checked, "failures": failures, "passed": checked > 0 and not failures}


def load_stage_config(path: Path) -> dict[str, Any]:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if config.get("status") != "frozen_before_e1_selection_outputs":
        raise RuntimeError("E1 selection config is not frozen")
    return config


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def judge_context(visible: Mapping[str, Any], features: Any) -> dict[str, Any]:
    transcript = list(visible.get("transcript") or [])
    last = transcript[-1] if transcript else {}
    public_result = {
        "error": visible.get("last_error") or last.get("error"),
        "output": last.get("output"),
    }
    return {
        "user_instruction": str(visible.get("instruction", "")),
        "failed_tool_name": str(features.tool_name),
        "failed_arguments": dict(features.failed_arguments),
        "public_error_or_return": public_result,
        "remaining_retry_budget": dict(visible.get("remaining_budget") or {}),
        "public_tool_schemas": list(visible.get("tool_schemas") or []),
        "observable_history": transcript,
    }


def prepare(config_path: Path) -> dict[str, Any]:
    config = load_stage_config(config_path)
    prerequisites = config["prerequisites"]
    p0_lock_path = root_path(prerequisites["p0_lock"])
    p0_manifest_path = root_path(prerequisites["p0_source_manifest"])
    if sha256_file(p0_lock_path) != str(prerequisites["p0_lock_sha256"]):
        raise RuntimeError("P0 lock hash mismatch")
    if sha256_file(p0_manifest_path) != str(prerequisites["p0_source_manifest_sha256"]):
        raise RuntimeError("P0 source-manifest hash mismatch")
    p0_lock = json.loads(p0_lock_path.read_text(encoding="utf-8"))
    if not p0_lock["authorization"]["e1_offline_selection"]:
        raise RuntimeError("P0 lock does not authorize E1 offline selection")
    source_verification = verify_source_manifest(p0_manifest_path)
    if not source_verification["passed"]:
        raise RuntimeError("P0 source-manifest verification failed")

    capacity_result_path = root_path(prerequisites["selector_capacity_result"])
    if sha256_file(capacity_result_path) != str(
        prerequisites["selector_capacity_result_sha256"]
    ):
        raise RuntimeError("selector-capacity result hash mismatch")
    locked_capacity = json.loads(capacity_result_path.read_text(encoding="utf-8"))
    if locked_capacity.get("status") != "complete":
        raise RuntimeError("selector-capacity result is incomplete")
    locked_by_instance = {
        str(record["instance_id"]): record for record in locked_capacity["records"]
    }

    capacity_config = capacity.load_config()
    formal_config = yaml.safe_load(capacity.FORMAL_RUNTIME_CONFIG.read_text(encoding="utf-8"))
    public_test = verify_test_file(formal_config)
    tasks = load_tasks(public_test.parent, str(formal_config["dataset"]["split"]))
    task_by_id = {task.task_id: task for task in tasks}
    sources, frozen_memory, portability = capacity.rebuild_frozen_memory_bank(
        capacity_config, formal_config
    )
    experiences = [as_experience(source) for source in sources]
    experiences_by_id = {item.experience_id: item for item in experiences}
    source_observations = {
        f"experience::{source.instance_id}": prepare_prefix(source)[1] for source in sources
    }
    ordered_experiences = sorted(experiences, key=lambda value: value.experience_id)
    memory_key_by_id = {
        experience.experience_id: f"M{index:03d}"
        for index, experience in enumerate(ordered_experiences, start=1)
    }
    retriever = SourceBlindTfidfRetriever(experiences)
    cohorts = capacity.load_cohort_records(capacity_config)
    variants = [str(value) for value in capacity_config["selector"]["variants"]]
    threshold = float(capacity_config["selector"]["minimum_extraction_confidence"])

    observable_targets: list[dict[str, Any]] = []
    deterministic_records: list[dict[str, Any]] = []
    oracle_records: list[dict[str, Any]] = []
    stratum_counts: dict[str, int] = {}
    target_index = 0
    for stratum, frozen_records in cohorts.items():
        stratum_counts[str(stratum)] = len(frozen_records)
        for frozen_record in frozen_records:
            target_index += 1
            target_key = f"T{target_index:04d}"
            source_task_id = str(frozen_record["source_task_id"])
            task = task_by_id.get(source_task_id)
            if task is None:
                raise RuntimeError(f"target task absent from public test: {source_task_id}")
            instance = capacity.build_instance(str(stratum), task)
            if instance is None or instance.instance_id != frozen_record["instance_id"]:
                raise RuntimeError(f"target reconstruction failed: {source_task_id}")
            ranked_all = retriever.retrieve(
                FailureQuery(instance.instance_id, instance.query_text, instance.provenance),
                top_k=len(experiences),
            )
            if len(ranked_all) != len(experiences):
                raise RuntimeError("source-target isolation removed an unexpected memory")
            ranked_top10 = ranked_all[:10]
            _, visible, prefix_sha256 = prepare_prefix(instance)
            if prefix_sha256 != frozen_record["prefix_sha256"]:
                raise RuntimeError(f"observable prefix mismatch: {instance.instance_id}")
            features = capacity.extract_failure_features(visible)
            candidates = capacity.public_candidates(
                ranked=ranked_top10,
                experience_by_id=experiences_by_id,
                source_observations=source_observations,
            )
            cards = [capacity.policy_card(candidate) for candidate in candidates]
            target = capacity.observable_failure(visible, features)
            decisions = {
                variant: capacity.select_from_mappings(
                    target.to_mapping(),
                    [card.to_mapping() for card in cards],
                    variant=capacity.SelectorVariant(variant),
                    minimum_extraction_confidence=threshold,
                ).to_mapping()
                for variant in variants
            }
            locked = locked_by_instance.get(instance.instance_id)
            if locked is None or locked["decisions"] != decisions:
                raise RuntimeError(f"selector decision differs from frozen audit: {instance.instance_id}")
            tfidf_id = ranked_all[0].experience.experience_id
            tfidf_key = memory_key_by_id[tfidf_id]
            observable_targets.append(
                {
                    "target_key": target_key,
                    "dense_query_text": instance.query_text,
                    "judge_context": judge_context(visible, features),
                    "tfidf_top10_memory_keys": [
                        memory_key_by_id[item.experience.experience_id]
                        for item in ranked_top10
                    ],
                }
            )
            deterministic_records.append(
                {
                    "target_key": target_key,
                    "stratum": str(stratum),
                    "instance_id": instance.instance_id,
                    "source_task_id": source_task_id,
                    "prefix_sha256": prefix_sha256,
                    "observable_target_sha256": canonical_sha256(target.to_mapping()),
                    "tfidf": {
                        "selected_memory_key": tfidf_key,
                        "selected_experience_id": tfidf_id,
                        "score": ranked_all[0].score,
                    },
                    "proper_variants": {
                        variant: {
                            "selected_memory_key": memory_key_by_id[
                                decisions[variant]["selected_experience_id"]
                            ],
                            "selected_experience_id": decisions[variant][
                                "selected_experience_id"
                            ],
                            "action": decisions[variant]["action"],
                            "selection_changed": decisions[variant]["selection_changed"],
                            "abstained": decisions[variant]["abstained"],
                            "reason_codes": decisions[variant]["reason_codes"],
                        }
                        for variant in variants
                    },
                }
            )

            oracle_ranked = []
            for item in ranked_all:
                signature = capacity.policy_signature(item.experience.policy)
                if signature not in instance.applicability:
                    raise RuntimeError(f"oracle applicability key absent: {signature}")
                oracle_ranked.append(
                    {
                        "memory_key": memory_key_by_id[item.experience.experience_id],
                        "experience_id": item.experience.experience_id,
                        "tfidf_rank": item.rank,
                        "policy_signature": signature,
                        "applicable": bool(instance.applicability[signature]),
                    }
                )
            oracle_selected = next(
                (item for item in oracle_ranked if item["applicable"]), None
            )
            oracle_records.append(
                {
                    "target_key": target_key,
                    "selected_memory_key": (
                        oracle_selected["memory_key"] if oracle_selected else None
                    ),
                    "selected_experience_id": (
                        oracle_selected["experience_id"] if oracle_selected else None
                    ),
                    "selected_tfidf_rank": (
                        oracle_selected["tfidf_rank"] if oracle_selected else None
                    ),
                    "no_applicable_memory": oracle_selected is None,
                    "ranked_applicability": oracle_ranked,
                }
            )

    expected_count = int(config["population"]["target_count"])
    if target_index != expected_count or len(locked_by_instance) != expected_count:
        raise RuntimeError("E1 target count mismatch")
    if stratum_counts != {
        key: int(value) for key, value in config["population"]["strata"].items()
    }:
        raise RuntimeError("E1 stratum counts differ from frozen config")

    observable = {
        "schema_version": 1,
        "stage_id": "e1_selection",
        "boundary": {
            "evaluator_labels_present": False,
            "source_identity_or_provenance_in_judge_prompt": False,
            "model_outputs_present": False,
        },
        "memory_key_policy": "lexical_experience_id_order_M001_through_M100",
        "memories": [
            {
                "memory_key": memory_key_by_id[item.experience_id],
                "natural_text": item.natural_text,
                "natural_text_sha256": hashlib.sha256(
                    item.natural_text.encode("utf-8")
                ).hexdigest(),
            }
            for item in ordered_experiences
        ],
        "targets": observable_targets,
    }
    deterministic = {
        "schema_version": 1,
        "stage_id": "e1_selection",
        "run_kind": "frozen_tfidf_and_proper_variant_selections",
        "boundary": {"model_loaded": False, "evaluator_labels_used": False},
        "records": deterministic_records,
    }
    oracle_private = {
        "schema_version": 1,
        "stage_id": "e1_selection",
        "visibility": "evaluator_only_never_model_input",
        "selection_policy": "first_applicable_in_full_tfidf_order_else_no_memory",
        "records": oracle_records,
    }

    outputs = config["preparation"]
    observable_path = root_path(outputs["observable_inputs"])
    deterministic_path = root_path(outputs["deterministic_selections"])
    oracle_path = root_path(outputs["oracle_private"])
    write_json(observable_path, observable)
    write_json(deterministic_path, deterministic)
    write_json(oracle_path, oracle_private)
    manifest = {
        "schema_version": 1,
        "status": "e1_inputs_prepared_before_dense_or_llm_judge_formal_outputs",
        "identities": {
            "config_path": str(config_path.relative_to(ROOT)).replace("\\", "/"),
            "config_sha256": sha256_file(config_path),
            "runner_path": str(Path(__file__).resolve().relative_to(ROOT)).replace("\\", "/"),
            "runner_sha256": sha256_file(Path(__file__).resolve()),
            "p0_lock_sha256": sha256_file(p0_lock_path),
            "p0_source_manifest_sha256": sha256_file(p0_manifest_path),
            "selector_capacity_result_sha256": sha256_file(capacity_result_path),
            "memory_payload_sha256": frozen_memory["identities"]["prepared_payload_sha256"],
            "memory_portability": portability,
        },
        "verification": {
            "p0_source_manifest": source_verification,
            "frozen_selector_decisions_reproduced": True,
        },
        "counts": {
            "targets": target_index,
            "memories": len(ordered_experiences),
            "strata": stratum_counts,
            "judge_prompts_planned": target_index,
            "dense_queries_planned": target_index,
        },
        "files": {
            "observable_inputs": {
                "path": str(observable_path.relative_to(ROOT)).replace("\\", "/"),
                "sha256": sha256_file(observable_path),
            },
            "deterministic_selections": {
                "path": str(deterministic_path.relative_to(ROOT)).replace("\\", "/"),
                "sha256": sha256_file(deterministic_path),
            },
            "oracle_private": {
                "path": str(oracle_path.relative_to(ROOT)).replace("\\", "/"),
                "sha256": sha256_file(oracle_path),
            },
        },
        "boundary": {
            "model_loaded": False,
            "model_outputs_read_or_generated": False,
            "formal_agent_generation_authorized": False,
        },
    }
    manifest_path = root_path(outputs["preparation_manifest"])
    write_json(manifest_path, manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare frozen, label-separated inputs for E1 offline selection."
    )
    parser.add_argument("--config", type=Path, default=CONFIG)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = prepare(args.config.resolve())
    print(json.dumps(manifest["counts"], indent=2, sort_keys=True))
    print(f"OUTPUT={root_path(load_stage_config(args.config.resolve())['preparation']['preparation_manifest'])}")
    print("NOTE=No model was loaded and no model output was read or generated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
