from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable

import yaml


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "external" / "toolmisusebench"))

from agent_runtime import (  # noqa: E402
    TransformersQwenClient,
    action_payload,
    build_prompt,
    canonical,
    execute_condition,
    parse_decision,
    prepare_prefix,
    sha256_file,
    sha256_text,
    verify_source_manifest,
)
from failure_memory.confirmatory import (  # noqa: E402
    aggregate_pair_indicators,
    behavior_atoms,
    indicators_payload,
    pair_indicators,
)
from failure_memory.contracts import PolicyKind, RecoveryPolicy  # noqa: E402
from failure_memory.retrieval import (  # noqa: E402
    Experience,
    FailureQuery,
    SourceBlindTfidfRetriever,
    tokenize,
)
from failure_memory.utilization import behavior_matches_policy  # noqa: E402
from failure_memory.versioning import resolve_versioned_artifact  # noqa: E402
from benchmark_instances import (  # noqa: E402
    RETRY_POLICY,
    REVISE_POLICY,
    SAMPLE,
    STOP_POLICY,
    PilotInstance,
    experience_text,
    make_actual_instance,
    make_argument_omission_instance,
    make_persistent_authz_instance,
    policy_signature,
)
from toolmisusebench.dataset import load_tasks  # noqa: E402
from toolmisusebench.types import Task  # noqa: E402


CONFIG = ROOT / "configs" / "proper_v1" / "memory_bank.yaml"
LOCK = ROOT / "configs" / "proper_v1" / "toolmisusebench.lock.json"

RECOVERY_SUFFIXES = {
    "retry": "I retried the original tool call once and the task goal was satisfied.",
    "revise_arguments": (
        "I corrected the missing arguments from the user instruction "
        "and the task goal was satisfied."
    ),
    "stop_and_report": (
        "I stopped without another tool call and reported that "
        "authorization was persistently denied."
    ),
}


def stable_key(seed: str, source_task_id: str) -> str:
    return sha256_text(f"{seed}:{source_task_id}")


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if config.get("status") != "refactored_runtime_after_completed_development_run":
        raise RuntimeError("memory-bank runtime configuration has an invalid status")
    return config


def resolve_root_path(value: str | Path) -> Path:
    return resolve_versioned_artifact(ROOT, value)


def task_fault(task: Task) -> str:
    return task.fault_plan[0].fault_type if task.fault_plan else "clean"


def source_builders() -> dict[str, tuple[str, Callable[[Task], PilotInstance | None]]]:
    return {
        "timeout_transient": (
            "timeout",
            lambda task: make_actual_instance(task, "timeout_transient", RETRY_POLICY),
        ),
        "schema_backend_one_shot": (
            "schema_drift",
            lambda task: make_actual_instance(task, "schema_backend_one_shot", RETRY_POLICY),
        ),
        "argument_omission_extension": ("clean", make_argument_omission_instance),
        "authorization_transient": (
            "authz",
            lambda task: make_actual_instance(task, "authorization_transient", RETRY_POLICY),
        ),
        "authorization_persistent_extension": ("authz", make_persistent_authz_instance),
    }


def load_exclusions(path: Path) -> tuple[set[str], dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    instance_ids = payload["retrieval_pilot_instance_ids"]
    source_ids = {value.split("::", 1)[0] for value in instance_ids}
    declared = set(payload["retrieval_pilot_source_task_ids"])
    if source_ids != declared or len(instance_ids) != 120 or len(declared) != 120:
        raise RuntimeError("pilot exclusion manifest must contain exactly the frozen 120 instances")
    agent_ids = set(payload["agent_pilot_instance_ids"])
    if len(agent_ids) != 20 or not agent_ids.issubset(set(instance_ids)):
        raise RuntimeError("agent pilot exclusion IDs must be a 20-instance pilot subset")
    return declared, payload


def build_memory_sources(
    tasks: list[Task], config: dict[str, Any], excluded: set[str]
) -> list[PilotInstance]:
    seed = str(config["selection"]["seed"])
    quotas = config["selection"]["memory_source_quotas"]
    by_fault: dict[str, list[Task]] = defaultdict(list)
    for task in tasks:
        if task.task_id not in excluded:
            by_fault[task_fault(task)].append(task)
    for values in by_fault.values():
        values.sort(key=lambda item: stable_key(seed, item.task_id))

    sources: list[PilotInstance] = []
    used: set[str] = set()
    for provenance, (fault, builder) in source_builders().items():
        quota = int(quotas[provenance])
        for task in by_fault[fault]:
            if task.task_id in used:
                continue
            instance = builder(task)
            if instance is not None:
                sources.append(instance)
                used.add(task.task_id)
            if sum(item.provenance == provenance for item in sources) == quota:
                break
        actual = sum(item.provenance == provenance for item in sources)
        if actual != quota:
            raise RuntimeError(
                f"memory source quota unavailable for {provenance}: {actual}/{quota}"
            )
    if len(used) != len(sources):
        raise AssertionError("one memory source per source task was violated")
    return sources


def build_targets(
    tasks: list[Task], config: dict[str, Any], excluded: set[str], source_ids: set[str]
) -> tuple[list[PilotInstance], dict[str, int]]:
    seed = str(config["selection"]["seed"])
    eligible = set(config["selection"]["eligible_source_faults"])
    candidates = [
        task
        for task in tasks
        if task_fault(task) in eligible
        and task.task_id not in excluded
        and task.task_id not in source_ids
    ]
    candidates.sort(key=lambda item: stable_key(seed, item.task_id))
    auth_index = 0
    targets: list[PilotInstance] = []
    rejected: Counter[str] = Counter()
    for task in candidates:
        fault = task_fault(task)
        if fault == "timeout":
            instance = make_actual_instance(task, "timeout_transient", RETRY_POLICY)
        elif fault == "schema_drift":
            instance = make_actual_instance(task, "schema_backend_one_shot", RETRY_POLICY)
        elif fault == "clean":
            instance = make_argument_omission_instance(task)
        elif fault == "authz":
            if auth_index % 2 == 0:
                instance = make_actual_instance(task, "authorization_transient", RETRY_POLICY)
            else:
                instance = make_persistent_authz_instance(task)
            auth_index += 1
        else:  # protected by eligible filter
            raise AssertionError(fault)
        if instance is None:
            rejected[fault] += 1
        else:
            targets.append(instance)
    if len({item.source_task_id for item in targets}) != len(targets):
        raise AssertionError("one target per source task was violated")
    return targets, dict(sorted(rejected.items()))


def as_experience(instance: PilotInstance) -> Experience:
    return Experience(
        experience_id=f"experience::{instance.instance_id}",
        source_instance_id=instance.instance_id,
        natural_text=experience_text(instance),
        policy=instance.recommended_policy,
        provenance=instance.provenance,
    )


def neutralize(experience: Experience, config: dict[str, Any]) -> str:
    suffix = RECOVERY_SUFFIXES[experience.policy.kind.value]
    if not experience.natural_text.endswith(suffix):
        raise RuntimeError(f"unknown recovery suffix: {experience.experience_id}")
    neutral = str(config["conditions"]["neutralized_recovery_text"])
    delta = abs(len(tokenize(neutral)) - len(tokenize(suffix)))
    maximum = int(config["conditions"]["neutralized_lexical_token_delta_max"])
    if delta > maximum:
        raise RuntimeError(f"neutralized lexical-token delta {delta} exceeds {maximum}")
    neutral_tokens = set(tokenize(neutral))
    forbidden = set(config["conditions"]["neutralized_forbidden_advice_tokens"])
    leaked = sorted(neutral_tokens & forbidden)
    if leaked:
        raise RuntimeError(f"neutralized memory contains frozen advice tokens: {leaked}")
    return experience.natural_text[: -len(suffix)] + neutral


def ensure_agent_boundary(prompts: Iterable[str], config: dict[str, Any]) -> None:
    forbidden = [str(value).lower() for value in config["agent_boundary"]["forbidden_agent_fields"]]
    for prompt in prompts:
        lowered = prompt.lower()
        leaked = [field for field in forbidden if field in lowered]
        if leaked:
            raise RuntimeError(f"evaluator-only field leaked into agent prompt: {leaked}")


def policy_payload(experience: Experience) -> dict[str, Any]:
    return {
        "kind": experience.policy.kind.value,
        "parameters": dict(experience.policy.parameters),
    }


def policy_from_payload(payload: dict[str, Any]) -> RecoveryPolicy:
    return RecoveryPolicy(PolicyKind(payload["kind"]), dict(payload["parameters"]))


def prepare_payload(config_path: Path = CONFIG) -> tuple[dict[str, Any], dict[str, Any]]:
    config = load_config(config_path)
    sample_path = SAMPLE / "dev.jsonl"
    expected_sample = str(config["dataset"]["sample_sha256"])
    if sha256_file(sample_path) != expected_sample:
        raise RuntimeError("dev sample hash does not match the frozen configuration")
    exclusion_path = resolve_root_path(config["pilot_exclusions"])
    excluded, exclusion_payload = load_exclusions(exclusion_path)
    upstream_manifest = resolve_root_path(config["dataset"]["toolmisusebench_source_manifest"])
    upstream_manifest_sha256 = verify_source_manifest(upstream_manifest)
    tasks = load_tasks(SAMPLE, str(config["dataset"]["split"]))
    eligible_faults = set(config["selection"]["eligible_source_faults"])
    sources = build_memory_sources(tasks, config, excluded)
    source_ids = {item.source_task_id for item in sources}
    targets, rejected = build_targets(tasks, config, excluded, source_ids)
    target_ids = {item.source_task_id for item in targets}
    if source_ids & target_ids or excluded & (source_ids | target_ids):
        raise AssertionError("pilot/source/target isolation failed")

    experiences = [as_experience(item) for item in sources]
    by_experience_id = {item.experience_id: item for item in experiences}
    retriever = SourceBlindTfidfRetriever(experiences)
    screening_records: list[dict[str, Any]] = []
    selected_pairs: list[dict[str, Any]] = []
    top_k = int(config["retrieval"]["top_k"])
    for instance in targets:
        ranked = retriever.retrieve(
            FailureQuery(instance.instance_id, instance.query_text, instance.provenance),
            top_k=len(experiences),
        )
        if not ranked:
            raise RuntimeError("empty retrieval result")
        selected = ranked[0].experience
        selected_applicable = instance.applicability[policy_signature(selected.policy)]
        matched = next(
            (
                item.experience
                for item in ranked
                if instance.applicability[policy_signature(item.experience.policy)]
            ),
            None,
        )
        record = {
            "instance_id": instance.instance_id,
            "source_task_id": instance.source_task_id,
            "failure_provenance": instance.provenance,
            "rank1_experience_id": selected.experience_id,
            "rank1_source_task_id": selected.source_instance_id.split("::", 1)[0],
            "rank1_applicable": selected_applicable,
            "rank1_score": round(ranked[0].score, 12),
            "matched_applicable_experience_id": matched.experience_id if matched else None,
            "top_k": [
                {
                    "rank": item.rank,
                    "experience_id": item.experience.experience_id,
                    "score": round(item.score, 12),
                    "applicable": instance.applicability[
                        policy_signature(item.experience.policy)
                    ],
                }
                for item in ranked[:top_k]
            ],
        }
        screening_records.append(record)
        if selected_applicable or matched is None:
            continue
        _, visible, prefix_sha256 = prepare_prefix(instance)
        prompts = {
            "no_memory": build_prompt(visible, None),
            "neutralized_memory": build_prompt(visible, neutralize(selected, config)),
            "inapplicable_memory": build_prompt(visible, selected.natural_text),
            "matched_applicable_memory": build_prompt(visible, matched.natural_text),
        }
        ensure_agent_boundary(prompts.values(), config)
        selected_pairs.append(
            {
                "instance_id": instance.instance_id,
                "source_task_id": instance.source_task_id,
                "failure_provenance": instance.provenance,
                "seed": instance.task.seed,
                "prefix_sha256": prefix_sha256,
                "failed_action": action_payload(instance.failure_action),
                "inapplicable_experience_id": selected.experience_id,
                "inapplicable_policy": policy_payload(selected),
                "matched_applicable_experience_id": matched.experience_id,
                "matched_applicable_policy": policy_payload(matched),
                "prompts": prompts,
                "prompt_sha256": {
                    name: sha256_text(value) for name, value in prompts.items()
                },
            }
        )

    minimum = int(config["selection"]["minimum_rank1_inapplicable_confirmatory_pairs"])
    preferred = int(config["selection"]["preferred_rank1_inapplicable_pairs"])
    screening = {
        "dev_task_count": len(tasks),
        "eligible_dev_task_count": sum(task_fault(item) in eligible_faults for item in tasks),
        "pilot_excluded_source_task_count": len(excluded),
        "memory_source_count": len(sources),
        "target_screened_count": len(targets),
        "target_rejected_counts": rejected,
        "rank1_inapplicable_count": sum(not item["rank1_applicable"] for item in screening_records),
        "matched_confirmatory_pair_count": len(selected_pairs),
        "minimum_required_pair_count": minimum,
        "preferred_pair_count": preferred,
        "minimum_met": len(selected_pairs) >= minimum,
        "preferred_met": len(selected_pairs) >= preferred,
        "gpu_run_authorized_by_capacity": len(selected_pairs) >= minimum,
    }
    payload = {
        "schema_version": 2,
        "run_kind": "confirmatory_v2_prepared",
        "identities": {
            "config_sha256": sha256_file(config_path),
            "dataset_revision": config["dataset"]["revision"],
            "dev_sample_sha256": sha256_file(sample_path),
            "pilot_exclusions_sha256": sha256_file(exclusion_path),
            "pilot_output_sha256": exclusion_payload["pilot_output_sha256"],
            "toolmisusebench_commit": config["dataset"]["toolmisusebench_commit"],
            "toolmisusebench_source_manifest_sha256": upstream_manifest_sha256,
        },
        "memory_sources": [
            {
                "experience_id": item.experience_id,
                "source_instance_id": item.source_instance_id,
                "source_task_id": item.source_instance_id.split("::", 1)[0],
                "provenance": item.provenance,
                "natural_text_sha256": sha256_text(item.natural_text),
                "policy": policy_payload(item),
            }
            for item in experiences
        ],
        "screening": screening,
        "records": screening_records,
        "selected_pairs": selected_pairs,
    }
    payload["identities"]["prepared_payload_sha256"] = sha256_text(canonical(payload))
    return payload, {item.instance_id: item for item in targets}


def write_prepared(payload: dict[str, Any], config: dict[str, Any]) -> None:
    prepared_path = resolve_root_path(config["outputs"]["prepared_manifest"])
    screening_path = resolve_root_path(config["outputs"]["screening_output"])
    prepared_path.parent.mkdir(parents=True, exist_ok=True)
    screening_path.parent.mkdir(parents=True, exist_ok=True)
    prepared_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    screening = {key: value for key, value in payload.items() if key != "selected_pairs"}
    screening["run_kind"] = "confirmatory_v2_screening"
    screening_path.write_text(
        json.dumps(screening, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def verify_model_files(model_path: Path, manifest_path: Path) -> None:
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        expected, separator, relative = line.partition("  ")
        if not separator or len(expected) != 64:
            raise RuntimeError(f"invalid model manifest line: {line!r}")
        relative = relative.removeprefix("./")
        candidate = (model_path / relative).resolve()
        try:
            candidate.relative_to(model_path.resolve())
        except ValueError as exc:
            raise RuntimeError(f"model manifest path escapes model root: {relative}") from exc
        if not candidate.is_file() or sha256_file(candidate) != expected:
            raise RuntimeError(f"model manifest mismatch: {relative}")


def condition_result(
    *, client: Any, instance: PilotInstance, prompt: str, seed: int
) -> tuple[Any, dict[str, Any]]:
    raw = client.complete(prompt, seed)
    decision, parse_valid, parse_error = parse_decision(raw)
    outcome, trace = execute_condition(instance, decision)
    correct_stop = (
        instance.provenance == "authorization_persistent_extension"
        and decision.kind.value == "stop"
        and decision.reason_code == "persistent_authorization_denial"
    )
    result = {
        "prompt": prompt,
        "prompt_sha256": sha256_text(prompt),
        "model_output": raw,
        "model_output_sha256": sha256_text(raw),
        "parse_valid": parse_valid,
        "parse_error": parse_error,
        **trace,
    }
    result["outcome"]["correct_stop"] = correct_stop
    return (decision, outcome), result


def run_conditional(args: argparse.Namespace, config: dict[str, Any]) -> int:
    prepared_path = resolve_root_path(config["outputs"]["prepared_manifest"])
    frozen = json.loads(prepared_path.read_text(encoding="utf-8"))
    rebuilt, target_by_id = prepare_payload(args.config)
    if canonical(frozen) != canonical(rebuilt):
        raise RuntimeError("prepared cohort does not match deterministic reconstruction")
    if not frozen["screening"]["gpu_run_authorized_by_capacity"]:
        raise RuntimeError("confirmatory cohort is below the frozen minimum; GPU run refused")

    project_manifest_sha256 = verify_source_manifest(args.project_manifest)
    model_manifest_sha256 = sha256_file(args.model_manifest)
    expected_model_manifest = str(config["model"]["manifest_sha256"])
    if model_manifest_sha256 != expected_model_manifest:
        raise RuntimeError("model manifest hash does not match frozen configuration")
    conda_lock_sha256 = sha256_file(args.conda_lock)
    pip_lock_sha256 = sha256_file(args.pip_lock)
    if conda_lock_sha256 != str(config["environment"]["conda_explicit_sha256"]):
        raise RuntimeError("conda explicit lock hash does not match frozen configuration")
    if pip_lock_sha256 != str(config["environment"]["pip_freeze_sha256"]):
        raise RuntimeError("pip freeze lock hash does not match frozen configuration")
    verify_model_files(args.model.resolve(), args.model_manifest)
    client = TransformersQwenClient(
        model_path=args.model.resolve(),
        load_in_4bit=args.load_in_4bit,
        max_new_tokens=int(config["model"]["max_new_tokens"]),
    )

    records: list[dict[str, Any]] = []
    indicators = []
    baseline_validity: list[bool] = []
    inapplicable_validity: list[bool] = []
    parse_failures = 0
    descriptive_validity: dict[str, list[bool]] = {
        condition: [] for condition in config["conditions"]["fixed_order"]
    }
    condition_outcomes: dict[str, list[Any]] = {
        condition: [] for condition in config["conditions"]["fixed_order"]
    }
    fixed_order = config["conditions"]["fixed_order"]
    for pair in frozen["selected_pairs"]:
        instance = target_by_id[pair["instance_id"]]
        condition_outputs: dict[str, Any] = {}
        decisions: dict[str, Any] = {}
        outcomes: dict[str, Any] = {}
        for condition in fixed_order:
            decision_outcome, result = condition_result(
                client=client,
                instance=instance,
                prompt=pair["prompts"][condition],
                seed=int(pair["seed"]),
            )
            decisions[condition], outcomes[condition] = decision_outcome
            condition_outputs[condition] = result
            parse_failures += int(not result["parse_valid"])
            descriptive_validity[condition].append(outcomes[condition].recovery_validity)
            condition_outcomes[condition].append(result["outcome"])

        prefix_hashes = {value["prefix_hash"] for value in condition_outputs.values()}
        if prefix_hashes != {pair["prefix_sha256"]}:
            raise RuntimeError(f"paired failure-prefix mismatch: {pair['instance_id']}")
        for condition in fixed_order:
            if condition_outputs[condition]["prompt_sha256"] != pair["prompt_sha256"][condition]:
                raise RuntimeError(f"prompt identity mismatch: {pair['instance_id']} {condition}")
            condition_outputs[condition]["behavior_atoms"] = behavior_atoms(
                failed_action=pair["failed_action"],
                no_memory_decision=decisions["no_memory"],
                condition_decision=decisions[condition],
                schema_verification_tools=config["behavior_atoms"][
                    "schema_verification_tools"
                ],
            )
        inapplicable_policy = policy_from_payload(pair["inapplicable_policy"])
        strict = condition_outputs["inapplicable_memory"]["parse_valid"] and (
            behavior_matches_policy(
                inapplicable_policy,
                failed_action=pair["failed_action"],
                decision=decisions["inapplicable_memory"],
                expected_revised_action=action_payload(instance.correct_action),
            )
        )
        indicator = pair_indicators(
            no_memory_recovery_validity=outcomes["no_memory"].recovery_validity,
            memory_recovery_validity=outcomes["inapplicable_memory"].recovery_validity,
            no_memory_decision=decisions["no_memory"],
            memory_decision=decisions["inapplicable_memory"],
            strict_policy_adoption=strict,
        )
        indicators.append(indicator)
        baseline_validity.append(outcomes["no_memory"].recovery_validity)
        inapplicable_validity.append(outcomes["inapplicable_memory"].recovery_validity)
        records.append(
            {
                **{key: value for key, value in pair.items() if key != "prompts"},
                "conditions": condition_outputs,
                "primary_pair_indicators": indicators_payload(indicator),
            }
        )

    aggregate = aggregate_pair_indicators(
        indicators,
        baseline_validity,
        inapplicable_validity,
        alpha=float(config["primary_endpoint"]["alpha"]),
    )
    pair_count = len(records)
    descriptive_controls = {}
    for condition in ("neutralized_memory", "matched_applicable_memory"):
        differences = [
            int(current) - int(baseline)
            for baseline, current in zip(
                descriptive_validity["no_memory"], descriptive_validity[condition], strict=True
            )
        ]
        descriptive_controls[f"{condition}_vs_no_memory"] = {
            "confirmatory_test_performed": False,
            "pair_count": pair_count,
            "negative_transfer_count": sum(value == -1 for value in differences),
            "positive_transfer_count": sum(value == 1 for value in differences),
            "net_paired_effect": sum(differences) / pair_count,
        }
    secondary_outcomes = {}
    for condition, outcomes_for_condition in condition_outcomes.items():
        secondary_outcomes[condition] = {
            "recovery_validity_count": sum(
                item["recovery_validity"] for item in outcomes_for_condition
            ),
            "task_completion_count": sum(
                item["task_completion"] for item in outcomes_for_condition
            ),
            "correct_stop_count": sum(item["correct_stop"] for item in outcomes_for_condition),
            "safety_violation_count": sum(
                item["safety_violation"] for item in outcomes_for_condition
            ),
            "repeated_invalid_calls_total": sum(
                item["repeated_invalid_calls"] for item in outcomes_for_condition
            ),
            "recovery_steps_total": sum(item["recovery_steps"] for item in outcomes_for_condition),
            "recovery_tool_calls_total": sum(
                item["recovery_tool_calls"] for item in outcomes_for_condition
            ),
        }
    report = {
        "schema_version": 2,
        "run_kind": "confirmatory_v2_conditional",
        "identities": {
            **frozen["identities"],
            "prepared_file_sha256": sha256_file(prepared_path),
            "project_source_manifest_sha256": project_manifest_sha256,
            "model_manifest_sha256": model_manifest_sha256,
            "conda_explicit_lock_sha256": conda_lock_sha256,
            "pip_freeze_lock_sha256": pip_lock_sha256,
            "toolmisusebench_lock_sha256": sha256_file(LOCK),
            "python": sys.version,
            "platform": platform.platform(),
        },
        "screening": frozen["screening"],
        "primary_comparison": aggregate,
        "descriptive_control_comparisons": descriptive_controls,
        "secondary_outcomes": secondary_outcomes,
        "model_output_parse_failure_count": parse_failures,
        "records": records,
    }
    output = resolve_root_path(config["outputs"]["conditional_output"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "records"}, indent=2))
    print("RESULT=COMPLETE_CONFIRMATORY_V2_CONDITIONAL")
    return 0


class SyntheticDryRunClient:
    """Non-model client used only to traverse the frozen CPU execution path."""

    def complete(self, prompt: str, seed: int) -> str:
        del prompt, seed
        return canonical({"kind": "stop", "reason_code": "synthetic_cpu_dry_run"})


def run_cpu_dry_run(config_path: Path, config: dict[str, Any]) -> int:
    payload, target_by_id = prepare_payload(config_path)
    if not payload["selected_pairs"]:
        raise RuntimeError("no selected pair is available for the CPU dry-run")
    pair = payload["selected_pairs"][0]
    instance = target_by_id[pair["instance_id"]]
    client = SyntheticDryRunClient()
    prefix_hashes: set[str] = set()
    parse_valid = []
    for condition in config["conditions"]["fixed_order"]:
        _, result = condition_result(
            client=client,
            instance=instance,
            prompt=pair["prompts"][condition],
            seed=int(pair["seed"]),
        )
        prefix_hashes.add(result["prefix_hash"])
        parse_valid.append(result["parse_valid"])
        if result["prompt_sha256"] != pair["prompt_sha256"][condition]:
            raise RuntimeError(f"CPU dry-run prompt mismatch: {condition}")
    if prefix_hashes != {pair["prefix_sha256"]} or not all(parse_valid):
        raise RuntimeError("CPU dry-run failed paired-prefix or parse validation")
    print(
        json.dumps(
            {
                "instance_id": pair["instance_id"],
                "condition_count": len(parse_valid),
                "synthetic_non_model_output": True,
                "model_loaded": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    print("RESULT=PASS_CONFIRMATORY_V2_CPU_DRY_RUN")
    print("NOTE=The synthetic client is not a research agent and produced no research result.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare or run frozen confirmatory-v2.")
    parser.add_argument("--config", type=Path, default=CONFIG)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true", help="CPU-only cohort and prompt dry-run")
    mode.add_argument(
        "--cpu-dry-run",
        action="store_true",
        help="exercise one four-condition path with a labeled synthetic client",
    )
    mode.add_argument(
        "--run-conditional", action="store_true", help="run the frozen GPU experiment"
    )
    parser.add_argument("--model", type=Path)
    parser.add_argument("--load-in-4bit", action="store_true")
    parser.add_argument("--conda-lock", type=Path)
    parser.add_argument("--pip-lock", type=Path)
    parser.add_argument("--model-manifest", type=Path)
    parser.add_argument("--project-manifest", type=Path)
    return parser.parse_args()


def require_formal_inputs(args: argparse.Namespace) -> None:
    required = ("model", "conda_lock", "pip_lock", "model_manifest", "project_manifest")
    missing = [name for name in required if getattr(args, name) is None]
    if missing:
        raise RuntimeError(f"missing formal inputs: {missing}")
    missing_files = [name for name in required if not Path(getattr(args, name)).exists()]
    if missing_files:
        raise RuntimeError(f"formal inputs do not exist: {missing_files}")


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    if args.prepare:
        payload, _ = prepare_payload(args.config)
        write_prepared(payload, config)
        print(json.dumps(payload["screening"], indent=2, sort_keys=True))
        result = (
            "PASS_CONFIRMATORY_V2_PREPARATION"
            if payload["screening"]["gpu_run_authorized_by_capacity"]
            else "STOP_CONFIRMATORY_V2_UNDERPOWERED"
        )
        print(f"RESULT={result}")
        print("NOTE=No model was loaded and no holdout model output was generated.")
        return 0
    if args.cpu_dry_run:
        return run_cpu_dry_run(args.config, config)
    require_formal_inputs(args)
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    return run_conditional(args, config)


if __name__ == "__main__":
    raise SystemExit(main())
