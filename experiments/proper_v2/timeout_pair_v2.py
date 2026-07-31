from __future__ import annotations

import argparse
import copy
import importlib.metadata
import json
import platform
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

import jsonschema
import yaml


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "external" / "toolmisusebench"))
sys.path.insert(0, str(ROOT / "experiments" / "proper_v1"))
sys.path.insert(0, str(ROOT / "experiments" / "proper_v2"))

from agent_runtime import (  # noqa: E402
    TransformersQwenClient,
    canonical,
    sha256_file,
    verify_source_manifest,
)
from gate_dataset import (  # noqa: E402
    condition_result,
    resolve_root_path,
    verify_model_files,
)
from failure_memory.confirmatory import (  # noqa: E402
    aggregate_pair_indicators,
    behavior_atoms,
    indicators_payload,
    pair_indicators,
)
from timeout_pair_preparation_v2 import prepare_payload  # noqa: E402


CONFIG = ROOT / "configs" / "proper_v2" / "timeout_pair_v2_formal.yaml"
FORMAL_LOCK = ROOT / "configs" / "proper_v2" / "timeout_pair_v2.lock.json"


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if config.get("status") != "frozen_before_timeout_model_outputs":
        raise RuntimeError("formal timeout-pair config has invalid status")
    return config


def verify_formal_lock() -> dict[str, Any]:
    lock = json.loads(FORMAL_LOCK.read_text(encoding="utf-8"))
    if lock.get("status") != "frozen_before_timeout_model_outputs":
        raise RuntimeError("formal timeout-pair lock has invalid status")
    for key in (
        "formal_config",
        "formal_runner",
        "preparation_config",
        "preparation_runner",
        "prepared_manifest",
        "preparation_screening",
        "capacity_config",
        "capacity_screening",
        "protocol",
        "result_schema",
        "source_manifest",
        "toolmisusebench_source_manifest",
        "environment_lock",
    ):
        item = lock[key]
        path = resolve_root_path(item["path"])
        if sha256_file(path) != str(item["sha256"]):
            raise RuntimeError(f"formal timeout source mismatch: {key}")
    if lock["model_outputs_generated"] or not lock["gpu_run_authorized"]:
        raise RuntimeError("formal timeout lock does not authorize frozen GPU run")
    toolmisusebench_manifest = lock["toolmisusebench_source_manifest"]
    if verify_source_manifest(
        resolve_root_path(toolmisusebench_manifest["path"])
    ) != str(toolmisusebench_manifest["sha256"]):
        raise RuntimeError("ToolMisuseBench source manifest verification failed")
    return lock


def verify_environment(config: Mapping[str, Any]) -> dict[str, Any]:
    value = config["environment"]
    path = resolve_root_path(value["lock"])
    if sha256_file(path) != str(value["lock_sha256"]):
        raise RuntimeError("timeout environment lock hash mismatch")
    lock = json.loads(path.read_text(encoding="utf-8"))
    for key in ("conda_explicit_lock", "pip_freeze_lock"):
        item = lock[key]
        if sha256_file(resolve_root_path(item["path"])) != str(item["sha256"]):
            raise RuntimeError(f"timeout environment artifact mismatch: {key}")
    if lock["conda_explicit_lock"]["sha256"] != str(
        value["conda_explicit_sha256"]
    ):
        raise RuntimeError("timeout config and conda lock disagree")
    if lock["pip_freeze_lock"]["sha256"] != str(value["pip_freeze_sha256"]):
        raise RuntimeError("timeout config and pip lock disagree")
    for distribution, expected in lock["required_distribution_versions"].items():
        actual = importlib.metadata.version(distribution)
        if actual != expected:
            raise RuntimeError(
                f"runtime distribution mismatch: {distribution} "
                f"expected={expected}, observed={actual}"
            )
    return lock


def load_prepared(
    config: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    value = config["preparation"]
    prepared_path = resolve_root_path(value["prepared_manifest"])
    screening_path = resolve_root_path(value["screening"])
    if sha256_file(prepared_path) != str(value["prepared_manifest_sha256"]):
        raise RuntimeError("prepared timeout manifest hash mismatch")
    if sha256_file(screening_path) != str(value["screening_sha256"]):
        raise RuntimeError("prepared timeout screening hash mismatch")
    frozen = json.loads(prepared_path.read_text(encoding="utf-8"))
    if frozen["identities"]["prepared_payload_sha256"] != str(
        value["prepared_payload_sha256"]
    ):
        raise RuntimeError("prepared timeout payload identity mismatch")
    expected = {
        "all_target_count": value["expected_all_target_count"],
        "primary_selection_changed_pair_count": value[
            "expected_primary_pair_count"
        ],
        "planned_model_call_count": value["expected_model_call_count"],
        "global_distinct_prompt_count": value[
            "expected_global_distinct_prompt_count"
        ],
    }
    for key, expected_value in expected.items():
        if frozen["screening"][key] != int(expected_value):
            raise RuntimeError(f"prepared timeout count mismatch: {key}")
    if frozen["boundary"]["model_loaded"] or frozen["boundary"]["model_outputs_read"]:
        raise RuntimeError("prepared timeout artifact contains model activity")

    rebuilt, instances = prepare_payload(resolve_root_path(value["config"]))
    if canonical(frozen) != canonical(rebuilt):
        raise RuntimeError("prepared timeout cohort does not reconstruct exactly")
    return frozen, instances


def aggregate_pairs(
    indicators: list[Any],
    baseline: list[bool],
    proper: list[bool],
    alpha: float,
) -> dict[str, Any]:
    result = aggregate_pair_indicators(indicators, baseline, proper, alpha=alpha)
    result["baseline_recovery_validity_count"] = sum(baseline)
    result["proper_recovery_validity_count"] = sum(proper)
    result["directional_hypothesis_supported"] = (
        result["paired_positive_transfer_count"]
        > result["paired_negative_transfer_count"]
        and result["exact_mcnemar_two_sided_p"] < alpha
    )
    result["hypothesis_direction"] = "ppt_greater_than_pnt"
    return result


def condition_summary(
    condition_rows: Mapping[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    result = {}
    for condition, rows in condition_rows.items():
        result[condition] = {
            "recovery_validity_count": sum(
                item["outcome"]["recovery_validity"] for item in rows
            ),
            "task_completion_count": sum(
                item["outcome"]["task_completion"] for item in rows
            ),
            "safety_violation_count": sum(
                item["outcome"]["safety_violation"] for item in rows
            ),
            "repeated_invalid_calls_total": sum(
                item["outcome"]["repeated_invalid_calls"] for item in rows
            ),
            "exact_retry_count": sum(
                item["behavior_atoms"]["exact_retry"] for item in rows
            ),
        }
    return result


def comparison_for_rows(
    rows: list[tuple[Any, bool, bool]], alpha: float
) -> dict[str, Any]:
    value = aggregate_pairs(
        [item[0] for item in rows],
        [item[1] for item in rows],
        [item[2] for item in rows],
        alpha,
    )
    value["confirmatory_test_performed"] = False
    return value


def run_formal(args: argparse.Namespace, config: dict[str, Any]) -> int:
    formal_lock = verify_formal_lock()
    verify_environment(config)
    frozen, instances = load_prepared(config)

    source_manifest_sha256 = verify_source_manifest(args.project_manifest)
    if source_manifest_sha256 != str(formal_lock["source_manifest"]["sha256"]):
        raise RuntimeError("provided project manifest differs from formal lock")
    verify_model_files(args.model.resolve(), args.model_manifest)
    if sha256_file(args.model_manifest) != str(config["model"]["manifest_sha256"]):
        raise RuntimeError("model manifest mismatch")
    if sha256_file(args.conda_lock) != str(
        config["environment"]["conda_explicit_sha256"]
    ):
        raise RuntimeError("conda explicit lock mismatch")
    if sha256_file(args.pip_lock) != str(config["environment"]["pip_freeze_sha256"]):
        raise RuntimeError("pip freeze lock mismatch")

    client = TransformersQwenClient(
        model_path=args.model.resolve(),
        load_in_4bit=args.load_in_4bit,
        max_new_tokens=int(config["model"]["max_new_tokens"]),
    )
    fixed_order = list(config["conditions"]["fixed_order"])
    baseline_name, proper_name = fixed_order
    output_records = []
    all_rows: list[tuple[Any, bool, bool]] = []
    primary_rows: list[tuple[Any, bool, bool]] = []
    condition_rows: dict[str, list[dict[str, Any]]] = {
        name: [] for name in fixed_order
    }
    tool_rows: dict[str, list[tuple[Any, bool, bool]]] = defaultdict(list)
    transition_rows: dict[str, list[tuple[Any, bool, bool]]] = defaultdict(list)
    model_call_count = 0
    parse_failures = 0

    for record in frozen["records"]:
        instance = instances[record["instance_id"]]
        conditions: dict[str, Any] = {}
        decisions: dict[str, Any] = {}
        outcomes: dict[str, Any] = {}
        completed: dict[str, tuple[Any, Any, dict[str, Any], str]] = {}
        for condition in fixed_order:
            prompt = record["prompts"][condition]
            prompt_hash = record["prompt_sha256"][condition]
            if prompt_hash in completed:
                decision, outcome, original_result, original_condition = completed[
                    prompt_hash
                ]
                result = copy.deepcopy(original_result)
                result["reused_from_condition"] = original_condition
            else:
                (decision, outcome), result = condition_result(
                    client=client,
                    instance=instance,
                    prompt=prompt,
                    seed=int(record["seed"]),
                )
                result["reused_from_condition"] = None
                completed[prompt_hash] = (
                    decision,
                    outcome,
                    copy.deepcopy(result),
                    condition,
                )
                model_call_count += 1
                parse_failures += int(not result["parse_valid"])
            if result["prompt_sha256"] != prompt_hash:
                raise RuntimeError("formal prompt identity mismatch")
            if result["prefix_hash"] != record["prefix_sha256"]:
                raise RuntimeError("paired failure prefix mismatch")
            decisions[condition] = decision
            outcomes[condition] = outcome
            conditions[condition] = result

        for condition in fixed_order:
            conditions[condition]["behavior_atoms"] = behavior_atoms(
                failed_action=record["failed_action"],
                no_memory_decision=decisions[baseline_name],
                condition_decision=decisions[condition],
                schema_verification_tools=(),
            )
            condition_rows[condition].append(conditions[condition])

        indicator = pair_indicators(
            no_memory_recovery_validity=outcomes[baseline_name].recovery_validity,
            memory_recovery_validity=outcomes[proper_name].recovery_validity,
            no_memory_decision=decisions[baseline_name],
            memory_decision=decisions[proper_name],
            strict_policy_adoption=conditions[proper_name]["behavior_atoms"][
                "exact_retry"
            ],
        )
        row = (
            indicator,
            outcomes[baseline_name].recovery_validity,
            outcomes[proper_name].recovery_validity,
        )
        all_rows.append(row)
        if record["selection_changed"]:
            primary_rows.append(row)
            tool_rows[record["target_tool_name"]].append(row)
            transition = (
                f"{record['rank1_operation']}->{record['proper_operation']}"
            )
            transition_rows[transition].append(row)
        output_records.append(
            {
                **{key: value for key, value in record.items() if key != "prompts"},
                "conditions": conditions,
                "proper_vs_rank1_indicators": indicators_payload(indicator),
            }
        )

    expected_calls = int(config["preparation"]["expected_model_call_count"])
    if model_call_count != expected_calls:
        raise RuntimeError("model call count differs from frozen protocol")
    alpha = float(config["primary_endpoint"]["alpha"])
    primary = comparison_for_rows(primary_rows, alpha)
    primary["confirmatory_test_performed"] = True
    all_targets = comparison_for_rows(all_rows, alpha)

    report = {
        "schema_version": 1,
        "run_kind": "proper_v2_timeout_pair_results",
        "identities": {
            **frozen["identities"],
            "prepared_file_sha256": sha256_file(
                resolve_root_path(config["preparation"]["prepared_manifest"])
            ),
            "formal_lock_sha256": sha256_file(FORMAL_LOCK),
            "project_source_manifest_sha256": source_manifest_sha256,
            "model_manifest_sha256": sha256_file(args.model_manifest),
            "conda_explicit_lock_sha256": sha256_file(args.conda_lock),
            "pip_freeze_lock_sha256": sha256_file(args.pip_lock),
            "python": sys.version,
            "platform": platform.platform(),
        },
        "screening": frozen["screening"],
        "primary_comparison": primary,
        "descriptive_all_targets": all_targets,
        "secondary_outcomes": {
            "conditions": condition_summary(condition_rows),
            "primary_target_tool_strata": {
                key: comparison_for_rows(rows, alpha)
                for key, rows in sorted(tool_rows.items())
            },
            "primary_operation_transition_strata": {
                key: comparison_for_rows(rows, alpha)
                for key, rows in sorted(transition_rows.items())
            },
            "primary_selected_memory_counts": dict(
                sorted(
                    Counter(
                        item["proper_experience_id"]
                        for item in frozen["records"]
                        if item["selection_changed"]
                    ).items()
                )
            ),
        },
        "model_output_parse_failure_count": parse_failures,
        "model_call_count": model_call_count,
        "records": output_records,
    }
    schema_path = resolve_root_path(config["outputs"]["result_schema"])
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(report, schema)

    output = resolve_root_path(config["outputs"]["result_output"])
    if output.exists():
        raise RuntimeError("refusing to overwrite a formal timeout result")
    for protected in config["outputs"]["never_overwrite"]:
        if output.resolve() == resolve_root_path(protected).resolve():
            raise RuntimeError("formal timeout output would overwrite prior evidence")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {key: value for key, value in report.items() if key != "records"},
            indent=2,
            sort_keys=True,
        )
    )
    print("RESULT=COMPLETE_PROPER_V2_TIMEOUT_PAIR")
    return 0


def cpu_dry_run(config: Mapping[str, Any]) -> dict[str, Any]:
    value = config["preparation"]
    prepared = json.loads(
        resolve_root_path(value["prepared_manifest"]).read_text(encoding="utf-8")
    )
    return {
        "model_loaded": False,
        "public_test_read": False,
        "model_outputs_read": False,
        "prepared_manifest_sha256_matches": sha256_file(
            resolve_root_path(value["prepared_manifest"])
        )
        == str(value["prepared_manifest_sha256"]),
        "all_target_count": prepared["screening"]["all_target_count"],
        "primary_pair_count": prepared["screening"][
            "primary_selection_changed_pair_count"
        ],
        "planned_model_call_count": prepared["screening"]["planned_model_call_count"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the frozen PROPER v2 timeout paired experiment."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--cpu-dry-run", action="store_true")
    mode.add_argument("--run", action="store_true")
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--load-in-4bit", action="store_true")
    parser.add_argument("--conda-lock", type=Path)
    parser.add_argument("--pip-lock", type=Path)
    parser.add_argument("--model-manifest", type=Path)
    parser.add_argument("--project-manifest", type=Path)
    return parser.parse_args()


def require_formal_inputs(args: argparse.Namespace) -> None:
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
    absent = [
        name for name in required if not Path(getattr(args, name)).exists()
    ]
    if absent:
        raise RuntimeError(f"formal inputs do not exist: {absent}")


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    if args.cpu_dry_run:
        lock = verify_formal_lock()
        verify_environment(config)
        result = cpu_dry_run(config)
        result["formal_lock_verified"] = True
        result["gpu_run_authorized_by_lock"] = bool(lock["gpu_run_authorized"])
        result["runtime_environment_verified"] = True
        print(json.dumps(result, indent=2, sort_keys=True))
        print("RESULT=PASS_PROPER_V2_TIMEOUT_PAIR_CPU_DRY_RUN")
        return 0
    require_formal_inputs(args)
    return run_formal(args, config)


if __name__ == "__main__":
    raise SystemExit(main())
