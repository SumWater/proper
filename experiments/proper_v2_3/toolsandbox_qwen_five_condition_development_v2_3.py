"""Frozen five-condition Qwen development runner for PROPER v2.3."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
V2 = ROOT / "experiments" / "proper_v2"
V23 = ROOT / "experiments" / "proper_v2_3"
for path in (V2, V23):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import continuation_development_v2_2_1 as continuation  # noqa: E402
import toolsandbox_model_pilot_runner_validation_v2_1 as engine  # noqa: E402
import toolsandbox_qwen_lifecycle_development_v2_2 as qwen_runtime  # noqa: E402
from failure_memory.proper_v2.v2_3 import ActionEffectClass  # noqa: E402
from toolsandbox_five_condition_provider_v2_3 import (  # noqa: E402
    FIFTH_CONDITION, FiveConditionProvider, PublicEffectRegistry,
)

CONFIG = ROOT / "configs" / "proper_v2_3" / "toolsandbox_qwen_five_condition_development_v2_3.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(ROOT), *args], check=True, capture_output=True,
        text=True, encoding="utf-8",
    ).stdout.strip()


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    config = load_json(path)
    if config.get("status") != "frozen_before_any_v2_3_qwen_output":
        raise RuntimeError("v2.3 Qwen config is not frozen")
    boundary = config["boundary"]
    if (
        not boundary["development_model_run_authorized"]
        or not boundary["existing_model_exposed_pairs"]
        or boundary["confirmatory_claim_authorized"]
        or boundary["heldout_claim_authorized"]
    ):
        raise RuntimeError("v2.3 Qwen authorization boundary is invalid")
    for item in config["frozen_inputs"]:
        target = ROOT / str(item["path"])
        if engine.sha256_file(target) != str(item["sha256"]):
            raise RuntimeError(f"frozen input mismatch: {item['path']}")
    return config


def verify_runtime(config: Mapping[str, Any], expected_revision: str) -> dict[str, Any]:
    policy = config["remote_execution"]
    if os.environ.get("PROPER_V2_3_EXECUTION_ROLE") != policy["execution_role"]:
        raise RuntimeError("v2.3 Qwen execution role is missing")
    if os.environ.get("CUDA_VISIBLE_DEVICES") != str(config["model"]["cuda_visible_devices"]):
        raise RuntimeError("CUDA device does not match frozen config")
    if not re.fullmatch(r"[0-9a-f]{40}", expected_revision):
        raise RuntimeError("expected revision must be a full Git commit")
    head = git("rev-parse", "HEAD")
    if head != expected_revision:
        raise RuntimeError(f"project revision mismatch: expected {expected_revision}, got {head}")
    if git("status", "--porcelain", "--untracked-files=no"):
        raise RuntimeError("tracked project worktree must be clean")
    return {
        "execution_role": policy["execution_role"],
        "project_revision": head,
        "tracked_worktree_clean": True,
        "python_version": platform.python_version(),
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
    }


def attempts(condition: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        attempt
        for decision in condition["decisions"]
        for attempt in decision.get("_model_attempts", [decision["_model"]])
    ]


def condition_metrics(condition: Mapping[str, Any]) -> dict[str, Any]:
    model_attempts = attempts(condition)
    decisions = condition["decisions"]
    return {
        "mean_similarity": float(condition["evaluation"]["similarity"]),
        "task_completed": condition["evaluation"]["similarity"] == 1.0,
        "first_decision_policy_alignment": bool(condition["first_decision_policy_alignment"]),
        "minefield": condition["evaluation"]["minefield_similarity"] > 0,
        "tool_exception_count": int(condition["tool_exception_count"]),
        "executed_identical_tool_call_count": int(condition["repeated_identical_tool_call_count"]),
        "accepted_decision_count": int(condition["recovery_decision_count"]),
        "native_tool_call_count": int(condition["recovery_tool_call_count"]),
        "model_request_count": len(model_attempts),
        "invalid_json_model_request_count": sum(
            not bool(item["valid_json_decision"]) for item in model_attempts
        ),
        "prompt_token_count": sum(
            int(item["usage"].get("prompt_token_count", 0)) for item in model_attempts
        ),
        "completion_token_count": sum(
            int(item["usage"].get("completion_token_count", 0)) for item in model_attempts
        ),
        "blocked_model_attempt_count": sum(
            len(decision.get("_controller", {}).get("blocked_attempts", []))
            for decision in decisions
        ),
    }


def summarize(records: list[dict[str, Any]], config: Mapping[str, Any]) -> dict[str, Any]:
    condition_names = [str(item["name"]) for item in config["conditions"]]
    report_names = {str(item["name"]): str(item["report_name"]) for item in config["conditions"]}
    phase_reports: dict[str, Any] = {}
    for phase in ("pre_action", "post_failure"):
        subset = [record for record in records if record["decision_phase"] == phase]
        phase_reports[phase] = {}
        for name in condition_names:
            metrics = [condition_metrics(record["conditions"][name]) for record in subset]
            phase_reports[phase][report_names[name]] = {
                "pair_count": len(metrics),
                "mean_similarity": sum(item["mean_similarity"] for item in metrics) / len(metrics),
                "task_completion_count": sum(item["task_completed"] for item in metrics),
                "first_decision_alignment_count": sum(item["first_decision_policy_alignment"] for item in metrics),
                "minefield_condition_count": sum(item["minefield"] for item in metrics),
                "tool_exception_count": sum(item["tool_exception_count"] for item in metrics),
                "executed_identical_tool_call_count": sum(item["executed_identical_tool_call_count"] for item in metrics),
                "model_request_count": sum(item["model_request_count"] for item in metrics),
                "native_tool_call_count": sum(item["native_tool_call_count"] for item in metrics),
                "prompt_token_count": sum(item["prompt_token_count"] for item in metrics),
                "completion_token_count": sum(item["completion_token_count"] for item in metrics),
                "blocked_model_attempt_count": sum(item["blocked_model_attempt_count"] for item in metrics),
            }

    fifth_conditions = [record["conditions"][FIFTH_CONDITION] for record in records]
    ledger_entries = [
        entry
        for condition in fifth_conditions
        for entry in condition["action_execution_guard"]["ledger"]["entries"]
    ]
    repeat_proposals = Counter()
    repeat_executions = Counter()
    duplicate_non_idempotent = 0
    outcome_unknown = 0
    verification_calls = 0
    for condition in fifth_conditions:
        entries = condition["action_execution_guard"]["ledger"]["entries"]
        by_identity: dict[str, list[Mapping[str, Any]]] = {}
        for entry in entries:
            identity = str(entry["action"]["normalized_identity"])
            prior = by_identity.setdefault(identity, [])
            effect = str(entry["effect_contract"]["effect_class"])
            if prior:
                repeat_proposals[effect] += 1
                if entry["status"] in {"succeeded", "failed", "outcome_unknown"}:
                    repeat_executions[effect] += 1
            prior.append(entry)
            outcome_unknown += entry["status"] == "outcome_unknown"
            verification_calls += entry["purpose"] == "verification" and entry["decision_allowed"]
        duplicate_non_idempotent += condition["execution_safety"]["duplicate_non_idempotent_execution_count"]
    all_attempts = [attempt for record in records for condition in record["conditions"].values() for attempt in attempts(condition)]
    endpoint_groups = {
        "selector": {
            "first_decision_alignment_by_phase_and_condition": {
                phase: {
                    condition: values["first_decision_alignment_count"]
                    for condition, values in report.items()
                }
                for phase, report in phase_reports.items()
            }
        },
        "lifecycle": {
            "final_status_counts": dict(sorted(Counter(
                condition["action_execution_guard"]["state"]["lifecycle_status"]
                for condition in fifth_conditions
            ).items())),
            "ordinary_planning_handoff_count": sum(
                condition["action_execution_guard"]["state"]["planning_mode"] == "ordinary_task_planning"
                for condition in fifth_conditions
            ),
        },
        "continuation": {
            "blocked_proposal_count": sum(
                condition["execution_safety"]["blocked_proposal_count"] for condition in fifth_conditions
            ),
            "all_allowed_executions_resolved": all(
                condition["execution_safety"]["all_allowed_executions_resolved"] for condition in fifth_conditions
            ),
        },
        "completion": {"phase_condition_reports": phase_reports},
        "safety": {
            "repeat_proposals_by_effect_class": dict(sorted(repeat_proposals.items())),
            "repeat_executions_by_effect_class": dict(sorted(repeat_executions.items())),
            "duplicate_non_idempotent_side_effect_count": duplicate_non_idempotent,
            "outcome_unknown_action_count": outcome_unknown,
            "verification_tool_call_count": verification_calls,
            "minefield_condition_count": sum(
                condition["evaluation"]["minefield_similarity"] > 0
                for record in records for condition in record["conditions"].values()
            ),
        },
        "cost": {
            "model_request_count": len(all_attempts),
            "accepted_decision_count": sum(
                condition["recovery_decision_count"]
                for record in records for condition in record["conditions"].values()
            ),
            "native_tool_call_count": sum(
                condition["recovery_tool_call_count"]
                for record in records for condition in record["conditions"].values()
            ),
            "prompt_token_count": sum(int(item["usage"].get("prompt_token_count", 0)) for item in all_attempts),
            "completion_token_count": sum(int(item["usage"].get("completion_token_count", 0)) for item in all_attempts),
        },
    }
    return {
        "pair_count": len(records),
        "condition_count": sum(len(record["conditions"]) for record in records),
        "phase_counts": dict(sorted(Counter(record["decision_phase"] for record in records).items())),
        "all_condition_starts_identical": all(record["identical_condition_start"] for record in records),
        "invalid_json_model_request_count": sum(not bool(item["valid_json_decision"]) for item in all_attempts),
        "endpoint_groups": endpoint_groups,
    }


def run_development(config_path: Path, expected_revision: str) -> dict[str, Any]:
    config = load_config(config_path)
    runtime = verify_runtime(config, expected_revision)
    engine_config_path = ROOT / str(config["engine_config"]["path"])
    stage_path = ROOT / str(config["lifecycle_config"]["path"])
    stage_config = continuation.load_config(stage_path)
    manifest = engine.load_manifest(load_json(engine_config_path))[1]
    pair_order = [str(item["pair_id"]) for item in manifest["records"]]
    prompts = load_json(ROOT / str(config["prompts"]["path"]))
    registry = PublicEffectRegistry(load_json(ROOT / str(config["effect_registry"]["path"])))
    smoke_pair = str(config["execution"]["smoke_pair_id"])
    print(f"STAGE=gpu_smoke pair={smoke_pair}", file=sys.stderr, flush=True)
    with qwen_runtime.JsonlWorkerClient(config) as client:
        provider = FiveConditionProvider(
            client=client, config=config, stage_config=stage_config,
            method_config=config, prompts=prompts, effect_registry=registry,
        )
        smoke = engine.run_validation(
            engine_config_path, decision_provider=provider, pair_ids={smoke_pair},
        )
        smoke_attempts = [
            attempt for condition in smoke["records"][0]["conditions"].values()
            for attempt in attempts(condition)
        ] if smoke["records"] else []
        smoke_passed = bool(smoke["records"]) and all(
            bool(attempt["valid_json_decision"]) for attempt in smoke_attempts
        )
        if not smoke_passed:
            if smoke["records"]:
                provider.finalize_records(smoke["records"])
            return {
                "schema_version": 1, "run_kind": "proper_v2_3_qwen_five_condition_smoke_stopped",
                "runtime": runtime, "smoke_pair_id": smoke_pair,
                "smoke_passed": False, "full_development_completed": False,
                "stage_gate_passed": False, "stop_reason": "gpu_smoke_failed",
                "records": smoke["records"], "model_request_log": client.requests,
                "boundary": dict(config["boundary"]),
            }
        remaining = set(pair_order) - {smoke_pair}
        print(f"STAGE=full_development remaining_pairs={len(remaining)}", file=sys.stderr, flush=True)
        remainder = engine.run_validation(
            engine_config_path, decision_provider=provider, pair_ids=remaining,
        )
        by_id = {str(item["pair_id"]): item for item in smoke["records"] + remainder["records"]}
        records = [by_id[pair_id] for pair_id in pair_order]
        provider.finalize_records(records)
        summary = summarize(records, config)
        integrity_passed = (
            summary["pair_count"] == 12
            and summary["condition_count"] == 60
            and summary["all_condition_starts_identical"]
            and summary["invalid_json_model_request_count"] == 0
            and summary["endpoint_groups"]["cost"]["model_request_count"] == len(client.requests)
            and summary["endpoint_groups"]["continuation"]["all_allowed_executions_resolved"]
        )
        safety_passed = summary["endpoint_groups"]["safety"]["duplicate_non_idempotent_side_effect_count"] == 0
        post = summary["endpoint_groups"]["completion"]["phase_condition_reports"]["post_failure"]
        completion_passed = (
            post["proper_v2_3_full_action_ledger_controller"]["task_completion_count"]
            > post["proper_v2_2_1_recovery_action_controller"]["task_completion_count"]
        )
        gate = integrity_passed and safety_passed and completion_passed
        stop_reasons = []
        if not integrity_passed:
            stop_reasons.append("integrity_or_accounting_failure")
        if not safety_passed:
            stop_reasons.append("duplicate_non_idempotent_side_effect")
        if not completion_passed:
            stop_reasons.append("post_failure_completion_not_strictly_better_than_condition_four")
        return {
            "schema_version": 1,
            "run_kind": "proper_v2_3_toolsandbox_qwen_five_condition_development",
            "runtime": runtime,
            "identities": {
                "config_sha256": engine.sha256_file(config_path),
                "frozen_input_sha256": {str(item["role"]): str(item["sha256"]) for item in config["frozen_inputs"]},
            },
            "smoke_pair_id": smoke_pair, "smoke_passed": True,
            "full_development_completed": integrity_passed,
            "stage_gate_passed": gate, "stop_reasons": stop_reasons,
            "summary": summary, "records": records,
            "model_request_log": client.requests,
            "model_protocol": dict(config["model"]),
            "boundary": dict(config["boundary"]),
            "interpretation_limits": dict(config["interpretation_limits"]),
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--expected-project-revision", required=True)
    args = parser.parse_args()
    config = load_config(args.config.resolve())
    started = datetime.now(timezone.utc)
    run_id = f"{started.strftime('%Y%m%dT%H%M%SZ')}-{platform.node().lower()}-{args.expected_project_revision[:12]}"
    output = ROOT / str(config["output"]["root"]) / run_id / "results.json"
    if output.exists():
        raise FileExistsError(f"refusing to overwrite model result: {output}")
    result = run_development(args.config.resolve(), args.expected_project_revision)
    result["run_id"] = run_id
    import jsonschema
    schema = load_json(
        ROOT / "schemas/proper_v2_3/qwen_five_condition_result.schema.json"
    )
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(result)
    write_json(output, result)
    print(json.dumps({
        "run_kind": result["run_kind"], "smoke_passed": result["smoke_passed"],
        "full_development_completed": result["full_development_completed"],
        "stage_gate_passed": result["stage_gate_passed"],
        "stop_reasons": result.get("stop_reasons", [result.get("stop_reason")]),
        "output": str(output),
    }, ensure_ascii=False, sort_keys=True))
    return 0 if result["stage_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
