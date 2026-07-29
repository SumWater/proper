from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

import yaml


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "external" / "toolmisusebench"))

from agent_runtime import (  # noqa: E402
    TransformersQwenClient,
    action_payload,
    build_prompt,
    canonical,
    prepare_prefix,
    sha256_file,
    sha256_text,
    verify_source_manifest,
)
from gate_dataset import (  # noqa: E402
    SAMPLE,
    SyntheticDryRunClient,
    as_experience,
    build_memory_sources,
    condition_result,
    ensure_agent_boundary,
    load_config as load_v2_config,
    load_exclusions,
    policy_payload,
    resolve_root_path,
    task_fault,
    verify_model_files,
)
from failure_memory.confirmatory import (  # noqa: E402
    aggregate_pair_indicators,
    behavior_atoms,
    indicators_payload,
    pair_indicators,
)
from failure_memory.frozen_gate import score_frozen_gate  # noqa: E402
from failure_memory.intervention_gate import extract_gate_features  # noqa: E402
from failure_memory.candidate_selector import (  # noqa: E402
    CandidateFeatures,
    FailureFeatures,
    RuleSet,
    extract_candidate_features,
    extract_failure_features,
    rerank_candidates,
    score_payload,
)
from failure_memory.retrieval import FailureQuery, SourceBlindTfidfRetriever  # noqa: E402
from candidate_manifest import candidate_payload, failure_payload  # noqa: E402
from benchmark_instances import make_argument_omission_instance, policy_signature  # noqa: E402
from toolmisusebench.dataset import load_tasks  # noqa: E402


CONFIG = ROOT / "configs" / "proper_v1" / "confirmatory_gate_v1.runtime.yaml"
SOURCE_LOCK = ROOT / "configs" / "proper_v1" / "confirmatory_gate_v1.runtime.lock.json"
TOOLMISUSEBENCH_LOCK = ROOT / "configs" / "proper_v1" / "toolmisusebench.lock.json"


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if payload.get("status") != "refactored_runtime_after_completed_formal_result":
        raise RuntimeError("confirmatory gate runtime configuration has an invalid status")
    return payload


def verify_source_lock() -> dict[str, Any]:
    lock = json.loads(SOURCE_LOCK.read_text(encoding="utf-8"))
    if lock.get("status") != "refactored_runtime_lock_after_completed_formal_result":
        raise RuntimeError("confirmatory gate runtime source lock has an invalid status")
    for key in ("config", "runner", "frozen_gate_source", "feature_source"):
        item = lock[key]
        if sha256_file(resolve_root_path(item["path"])) != item["sha256"]:
            raise RuntimeError(f"confirmatory gate locked file changed: {key}")
    return lock


def stable_key(seed: str, source_task_id: str) -> str:
    return sha256_text(f"{seed}:{source_task_id}")


def test_file(config: Mapping[str, Any]) -> Path:
    dataset = config["dataset"]
    return ROOT / dataset["local_directory"] / dataset["local_filename"]


def verify_test_file(config: Mapping[str, Any]) -> Path:
    path = test_file(config)
    if not path.is_file():
        raise FileNotFoundError(
            f"frozen public-test file is absent: {path}; acquisition is a separate reviewed step"
        )
    if path.stat().st_size != int(config["dataset"]["expected_bytes"]):
        raise RuntimeError("public-test byte count mismatch")
    if sha256_file(path) != str(config["dataset"]["sha256"]):
        raise RuntimeError("public-test SHA256 mismatch")
    return path


def load_gate_artifact(config: Mapping[str, Any]) -> dict[str, Any]:
    path = resolve_root_path(config["development_dependencies"]["gate_artifact"])
    if sha256_file(path) != str(
        config["development_dependencies"]["gate_artifact_sha256"]
    ):
        raise RuntimeError("frozen gate artifact mismatch")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload["final_model"]["model_payload_sha256"] != str(
        config["development_dependencies"]["gate_model_payload_sha256"]
    ):
        raise RuntimeError("frozen gate model payload mismatch")
    return payload


def load_rules(config: Mapping[str, Any]) -> RuleSet:
    path = resolve_root_path(config["development_dependencies"]["candidate_rules"])
    if sha256_file(path) != str(
        config["development_dependencies"]["candidate_rules_sha256"]
    ):
        raise RuntimeError("frozen PROPER v1 rules mismatch")
    source = resolve_root_path(config["development_dependencies"]["candidate_selector_source"])
    if sha256_file(source) != str(
        config["development_dependencies"]["candidate_selector_source_sha256"]
    ):
        raise RuntimeError("frozen PROPER v1 source mismatch")
    return RuleSet.from_mapping(yaml.safe_load(path.read_text(encoding="utf-8")))


def frozen_memory_bank(config: Mapping[str, Any]) -> tuple[list[Any], dict[str, Any]]:
    dependencies = config["development_dependencies"]
    prepared_path = resolve_root_path(dependencies["frozen_memory_bank_manifest"])
    if sha256_file(prepared_path) != str(
        dependencies["frozen_memory_bank_manifest_sha256"]
    ):
        raise RuntimeError("frozen dev memory-bank manifest mismatch")
    frozen = json.loads(prepared_path.read_text(encoding="utf-8"))
    v2_config = load_v2_config()
    exclusions, _ = load_exclusions(resolve_root_path(v2_config["pilot_exclusions"]))
    dev_path = SAMPLE / "dev.jsonl"
    if sha256_file(dev_path) != str(dependencies["dev_sample_sha256"]):
        raise RuntimeError("frozen dev sample mismatch")
    dev_tasks = load_tasks(SAMPLE, "dev")
    sources = build_memory_sources(dev_tasks, v2_config, exclusions)
    experiences = [as_experience(source) for source in sources]
    rebuilt = {
        item.experience_id: {
            "source_task_id": item.source_instance_id.split("::", 1)[0],
            "natural_text_sha256": sha256_text(item.natural_text),
        }
        for item in experiences
    }
    declared = {
        item["experience_id"]: {
            "source_task_id": item["source_task_id"],
            "natural_text_sha256": item["natural_text_sha256"],
        }
        for item in frozen["memory_sources"]
    }
    if rebuilt != declared or len(experiences) != int(dependencies["memory_source_count"]):
        raise RuntimeError("rebuilt dev memory bank differs from frozen 100-source bank")
    return sources, frozen


def target_candidates(
    *,
    instance: Any,
    ranked: list[Any],
    experience_by_id: Mapping[str, Any],
    source_observations: Mapping[str, Mapping[str, Any]],
    rules: RuleSet,
) -> tuple[FailureFeatures, list[CandidateFeatures], list[Any], dict[str, Any]]:
    _, visible, prefix_sha256 = prepare_prefix(instance)
    target_features = extract_failure_features(visible)
    candidates = [
        extract_candidate_features(
            experience_id=item.experience.experience_id,
            natural_text=experience_by_id[item.experience.experience_id].natural_text,
            original_rank=item.rank,
            tfidf_score=round(item.score, 12),
            source_observation=source_observations[item.experience.experience_id],
        )
        for item in ranked
    ]
    reranked = rerank_candidates(target=target_features, candidates=candidates, rules=rules)
    record = {
        "target_features": failure_payload(target_features),
        "proper_selected_experience_id": reranked[0].candidate.experience_id,
        "proper_top10": [
            {
                "proper_rank": item.proper_rank,
                "candidate": candidate_payload(item.candidate),
                "score": score_payload(item.score),
                "evaluator_only_environment_applicable": instance.applicability[
                    policy_signature(experience_by_id[item.candidate.experience_id].policy)
                ],
            }
            for item in reranked
        ],
    }
    return target_features, candidates, reranked, {
        "visible": visible,
        "prefix_sha256": prefix_sha256,
        "gate_record": record,
    }


def prepare_payload(config_path: Path = CONFIG) -> tuple[dict[str, Any], dict[str, Any]]:
    verify_source_lock()
    config = load_config(config_path)
    public_test = verify_test_file(config)
    gate_artifact = load_gate_artifact(config)
    rules = load_rules(config)
    sources, frozen_memory = frozen_memory_bank(config)
    experiences = [as_experience(source) for source in sources]
    experience_by_id = {item.experience_id: item for item in experiences}
    source_observations = {
        f"experience::{source.instance_id}": prepare_prefix(source)[1]
        for source in sources
    }
    retriever = SourceBlindTfidfRetriever(experiences)

    test_root = public_test.parent
    tasks = load_tasks(test_root, str(config["dataset"]["split"]))
    if len(tasks) != int(config["dataset"]["expected_task_count"]):
        raise RuntimeError("public-test task count mismatch")
    clean_tasks = [task for task in tasks if task_fault(task) == "clean"]
    clean_tasks.sort(
        key=lambda task: stable_key(
            str(config["target_cohort"]["seed"]), task.task_id
        )
    )

    targets = []
    rejected = 0
    for task in clean_tasks:
        instance = make_argument_omission_instance(task)
        if instance is None:
            rejected += 1
        else:
            targets.append(instance)

    records = []
    target_by_id = {target.instance_id: target for target in targets}
    for instance in targets:
        all_ranked = retriever.retrieve(
            FailureQuery(instance.instance_id, instance.query_text, instance.provenance),
            top_k=len(experiences),
        )
        top10 = all_ranked[: int(config["retrieval"]["top_k_for_gate_and_reranker"])]
        _, _, _, built = target_candidates(
            instance=instance,
            ranked=top10,
            experience_by_id=experience_by_id,
            source_observations=source_observations,
            rules=rules,
        )
        gate_features = extract_gate_features(built["gate_record"])
        gate_decision = score_frozen_gate(gate_features, gate_artifact["final_model"])
        rank1 = top10[0].experience
        proper_id = built["gate_record"]["proper_selected_experience_id"]
        selected_id = proper_id if gate_decision.intervene else rank1.experience_id
        selected = experience_by_id[selected_id]
        matched = next(
            (
                item.experience
                for item in all_ranked
                if instance.applicability[policy_signature(item.experience.policy)]
            ),
            None,
        )
        if matched is None:
            raise RuntimeError(f"no applicable dev-memory control for {instance.instance_id}")
        prompts = {
            "no_memory": build_prompt(built["visible"], None),
            "tfidf_rank1_memory": build_prompt(built["visible"], rank1.natural_text),
            "proper_gate_memory": build_prompt(built["visible"], selected.natural_text),
            "matched_applicable_memory": build_prompt(
                built["visible"], matched.natural_text
            ),
        }
        ensure_agent_boundary(prompts.values(), load_v2_config())
        records.append(
            {
                "instance_id": instance.instance_id,
                "source_task_id": instance.source_task_id,
                "extension": "argument_omission_extension",
                "seed": instance.task.seed,
                "prefix_sha256": built["prefix_sha256"],
                "failed_action": action_payload(instance.failure_action),
                "rank1_experience_id": rank1.experience_id,
                "proper_v1_experience_id": proper_id,
                "gate_selected_experience_id": selected_id,
                "gate_probability": gate_decision.probability,
                "gate_intervene": gate_decision.intervene,
                "gate_selection_changed": selected_id != rank1.experience_id,
                "matched_applicable_experience_id": matched.experience_id,
                "evaluator_only": {
                    "rank1_applicable": instance.applicability[
                        policy_signature(rank1.policy)
                    ],
                    "gate_selected_applicable": instance.applicability[
                        policy_signature(selected.policy)
                    ],
                },
                "prompts": prompts,
                "prompt_sha256": {
                    name: sha256_text(prompt) for name, prompt in prompts.items()
                },
                "gate_feature_sha256": sha256_text(canonical(gate_features)),
            }
        )

    primary_count = sum(record["gate_selection_changed"] for record in records)
    minimum = int(config["target_cohort"]["minimum_gate_changed_primary_pairs"])
    preferred = int(config["target_cohort"]["preferred_gate_changed_primary_pairs"])
    screening = {
        "public_test_task_count": len(tasks),
        "clean_base_task_count": len(clean_tasks),
        "valid_argument_omission_target_count": len(records),
        "rejected_argument_omission_target_count": rejected,
        "gate_intervention_count": sum(record["gate_intervene"] for record in records),
        "gate_changed_primary_pair_count": primary_count,
        "minimum_required_primary_pair_count": minimum,
        "preferred_primary_pair_count": preferred,
        "minimum_met": primary_count >= minimum,
        "preferred_met": primary_count >= preferred,
        "gpu_run_authorized_by_capacity": primary_count >= minimum,
    }
    payload = {
        "schema_version": 1,
        "run_kind": "confirmatory_gate_v1_prepared",
        "identities": {
            "config_sha256": sha256_file(config_path),
            "source_lock_sha256": sha256_file(SOURCE_LOCK),
            "test_public_sha256": sha256_file(public_test),
            "gate_artifact_sha256": sha256_file(
                resolve_root_path(config["development_dependencies"]["gate_artifact"])
            ),
            "frozen_memory_bank_manifest_sha256": sha256_file(
                resolve_root_path(
                    config["development_dependencies"]["frozen_memory_bank_manifest"]
                )
            ),
            "frozen_memory_bank_payload_sha256": frozen_memory["identities"][
                "prepared_payload_sha256"
            ],
        },
        "boundary": {
            "model_loaded": False,
            "model_outputs_read": False,
            "test_labels_used_by_gate": False,
            "memory_source_split": "dev",
            "target_split": "test_public",
            "local_extension": "argument_omission_extension",
        },
        "screening": screening,
        "memory_sources": frozen_memory["memory_sources"],
        "records": records,
    }
    payload["identities"]["prepared_payload_sha256"] = sha256_text(canonical(payload))
    return payload, target_by_id


def write_prepared(payload: dict[str, Any], config: Mapping[str, Any]) -> None:
    prepared = resolve_root_path(config["outputs"]["prepared_manifest"])
    screening = resolve_root_path(config["outputs"]["screening_output"])
    prepared.parent.mkdir(parents=True, exist_ok=True)
    screening.parent.mkdir(parents=True, exist_ok=True)
    prepared.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    screening_payload = {key: value for key, value in payload.items() if key != "records"}
    screening_payload["run_kind"] = "confirmatory_gate_v1_screening"
    screening.write_text(
        json.dumps(screening_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def aggregate_primary(rows: list[dict[str, Any]], alpha: float) -> dict[str, Any]:
    indicators = [row["indicator"] for row in rows]
    rank1 = [row["rank1_recovery_validity"] for row in rows]
    gate = [row["gate_recovery_validity"] for row in rows]
    aggregate = aggregate_pair_indicators(indicators, rank1, gate, alpha=alpha)
    aggregate["directional_hypothesis_supported"] = (
        aggregate["paired_positive_transfer_count"]
        > aggregate["paired_negative_transfer_count"]
        and aggregate["exact_mcnemar_two_sided_p"] < alpha
    )
    aggregate["hypothesis_direction"] = "ppt_greater_than_pnt"
    return aggregate


def run_formal(args: argparse.Namespace, config: dict[str, Any]) -> int:
    prepared_path = resolve_root_path(config["outputs"]["prepared_manifest"])
    frozen = json.loads(prepared_path.read_text(encoding="utf-8"))
    rebuilt, target_by_id = prepare_payload(args.config)
    if canonical(frozen) != canonical(rebuilt):
        raise RuntimeError("prepared public-test cohort does not reconstruct exactly")
    if not frozen["screening"]["gpu_run_authorized_by_capacity"]:
        raise RuntimeError("frozen public-test cohort is below minimum; GPU run refused")

    project_manifest_sha256 = verify_source_manifest(args.project_manifest)
    verify_model_files(args.model.resolve(), args.model_manifest)
    if sha256_file(args.model_manifest) != str(config["model"]["manifest_sha256"]):
        raise RuntimeError("model manifest mismatch")
    if sha256_file(args.conda_lock) != str(
        config["environment"]["conda_explicit_sha256"]
    ):
        raise RuntimeError("conda environment lock mismatch")
    if sha256_file(args.pip_lock) != str(config["environment"]["pip_freeze_sha256"]):
        raise RuntimeError("pip environment lock mismatch")

    client = TransformersQwenClient(
        model_path=args.model.resolve(),
        load_in_4bit=args.load_in_4bit,
        max_new_tokens=int(config["model"]["max_new_tokens"]),
    )
    output_records = []
    parse_failures = 0
    for record in frozen["records"]:
        instance = target_by_id[record["instance_id"]]
        condition_outputs: dict[str, Any] = {}
        decisions: dict[str, Any] = {}
        outcomes: dict[str, Any] = {}
        completed_by_prompt: dict[str, tuple[Any, Any, dict[str, Any], str]] = {}
        for condition in config["conditions"]["fixed_order"]:
            prompt = record["prompts"][condition]
            prompt_hash = record["prompt_sha256"][condition]
            if prompt_hash in completed_by_prompt:
                decision, outcome, result, original_condition = completed_by_prompt[prompt_hash]
                result = dict(result)
                result["reused_from_condition"] = original_condition
            else:
                (decision, outcome), result = condition_result(
                    client=client,
                    instance=instance,
                    prompt=prompt,
                    seed=int(record["seed"]),
                )
                result["reused_from_condition"] = None
                completed_by_prompt[prompt_hash] = (
                    decision,
                    outcome,
                    result,
                    condition,
                )
            if result["prompt_sha256"] != prompt_hash:
                raise RuntimeError(f"prompt identity mismatch: {record['instance_id']}")
            decisions[condition] = decision
            outcomes[condition] = outcome
            condition_outputs[condition] = result
            parse_failures += int(not result["parse_valid"])

        indicator = pair_indicators(
            no_memory_recovery_validity=outcomes[
                "tfidf_rank1_memory"
            ].recovery_validity,
            memory_recovery_validity=outcomes["proper_gate_memory"].recovery_validity,
            no_memory_decision=decisions["tfidf_rank1_memory"],
            memory_decision=decisions["proper_gate_memory"],
            strict_policy_adoption=False,
        )
        atoms = behavior_atoms(
            failed_action=record["failed_action"],
            no_memory_decision=decisions["tfidf_rank1_memory"],
            condition_decision=decisions["proper_gate_memory"],
            schema_verification_tools=(),
        )
        output_records.append(
            {
                **{key: value for key, value in record.items() if key != "prompts"},
                "conditions": condition_outputs,
                "gate_vs_rank1_indicators": indicators_payload(indicator),
                "gate_vs_rank1_behavior_atoms": atoms,
            }
        )

    primary_rows = []
    for prepared_record, result_record in zip(
        frozen["records"], output_records, strict=True
    ):
        if not prepared_record["gate_selection_changed"]:
            continue
        indicators = pair_indicators(
            no_memory_recovery_validity=result_record["conditions"][
                "tfidf_rank1_memory"
            ]["outcome"]["recovery_validity"],
            memory_recovery_validity=result_record["conditions"][
                "proper_gate_memory"
            ]["outcome"]["recovery_validity"],
            no_memory_decision=decisions_from_result(
                result_record["conditions"]["tfidf_rank1_memory"]["decision"]
            ),
            memory_decision=decisions_from_result(
                result_record["conditions"]["proper_gate_memory"]["decision"]
            ),
            strict_policy_adoption=False,
        )
        primary_rows.append(
            {
                "indicator": indicators,
                "rank1_recovery_validity": result_record["conditions"][
                    "tfidf_rank1_memory"
                ]["outcome"]["recovery_validity"],
                "gate_recovery_validity": result_record["conditions"][
                    "proper_gate_memory"
                ]["outcome"]["recovery_validity"],
            }
        )
    alpha = float(config["primary_endpoint"]["alpha"])
    primary = aggregate_primary(primary_rows, alpha)
    report = {
        "schema_version": 1,
        "run_kind": "confirmatory_gate_v1_results",
        "identities": {
            **frozen["identities"],
            "prepared_file_sha256": sha256_file(prepared_path),
            "project_source_manifest_sha256": project_manifest_sha256,
            "model_manifest_sha256": sha256_file(args.model_manifest),
            "conda_explicit_lock_sha256": sha256_file(args.conda_lock),
            "pip_freeze_lock_sha256": sha256_file(args.pip_lock),
            "toolmisusebench_lock_sha256": sha256_file(TOOLMISUSEBENCH_LOCK),
            "python": sys.version,
            "platform": platform.platform(),
        },
        "screening": frozen["screening"],
        "primary_comparison": primary,
        "model_output_parse_failure_count": parse_failures,
        "records": output_records,
    }
    output_path = resolve_root_path(config["outputs"]["result_output"])
    for protected in config["outputs"]["never_overwrite"]:
        if output_path.resolve() == resolve_root_path(protected).resolve():
            raise RuntimeError("confirmatory gate output would overwrite prior evidence")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({key: value for key, value in report.items() if key != "records"}, indent=2))
    print("RESULT=COMPLETE_CONFIRMATORY_GATE_V1")
    return 0


def decisions_from_result(payload: Mapping[str, Any]) -> Any:
    from failure_memory.utilization import AgentDecision, DecisionKind

    if payload["kind"] == "tool":
        return AgentDecision(
            DecisionKind.TOOL,
            tool_name=str(payload["tool_name"]),
            args=dict(payload["args"]),
        )
    return AgentDecision(DecisionKind.STOP, reason_code=str(payload["reason_code"]))


def run_cpu_dry_run() -> int:
    verify_source_lock()
    config = load_config()
    artifact = load_gate_artifact(config)
    development = json.loads(
        (ROOT / "outputs" / "proper_v1" / "candidate_selection" / "selection_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    gate_features = extract_gate_features(development["records"][0])
    gate_decision = score_frozen_gate(gate_features, artifact["final_model"])

    from gate_dataset import prepare_payload as prepare_memory_bank_payload

    prepared, target_by_id = prepare_memory_bank_payload()
    pair = prepared["selected_pairs"][0]
    instance = target_by_id[pair["instance_id"]]
    client = SyntheticDryRunClient()
    prompt_hashes = []
    for condition in ("no_memory", "inapplicable_memory"):
        _, result = condition_result(
            client=client,
            instance=instance,
            prompt=pair["prompts"][condition],
            seed=int(pair["seed"]),
        )
        prompt_hashes.append(result["prompt_sha256"])
        if not result["parse_valid"]:
            raise RuntimeError("synthetic dry-run decision failed parsing")
    print(
        json.dumps(
            {
                "gate_probability": gate_decision.probability,
                "gate_threshold": gate_decision.threshold,
                "condition_count": 2,
                "distinct_prompt_count": len(set(prompt_hashes)),
                "synthetic_non_model_output": True,
                "public_test_read": False,
                "model_loaded": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    print("RESULT=PASS_CONFIRMATORY_GATE_V1_CPU_DRY_RUN")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare or run Confirmatory Gate v1")
    parser.add_argument("--config", type=Path, default=CONFIG)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--cpu-dry-run", action="store_true")
    mode.add_argument("--run", action="store_true")
    parser.add_argument("--model", type=Path)
    parser.add_argument("--load-in-4bit", action="store_true")
    parser.add_argument("--conda-lock", type=Path)
    parser.add_argument("--pip-lock", type=Path)
    parser.add_argument("--model-manifest", type=Path)
    parser.add_argument("--project-manifest", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    if args.cpu_dry_run:
        return run_cpu_dry_run()
    if args.prepare:
        payload, _ = prepare_payload(args.config)
        write_prepared(payload, config)
        print(json.dumps(payload["screening"], indent=2, sort_keys=True))
        result = (
            "PASS_CONFIRMATORY_GATE_V1_PREPARATION"
            if payload["screening"]["gpu_run_authorized_by_capacity"]
            else "STOP_CONFIRMATORY_GATE_V1_UNDERPOWERED"
        )
        print(f"RESULT={result}")
        print("NOTE=No model was loaded and no public-test model output was generated.")
        return 0
    required = (
        "model",
        "conda_lock",
        "pip_lock",
        "model_manifest",
        "project_manifest",
    )
    missing = [name for name in required if getattr(args, name) is None]
    if missing:
        raise RuntimeError(f"missing formal inputs: {missing}")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    return run_formal(args, config)


if __name__ == "__main__":
    raise SystemExit(main())
