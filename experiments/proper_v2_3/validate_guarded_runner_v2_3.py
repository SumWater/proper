"""CPU-only end-to-end validation of the five-condition runner adapter."""

from __future__ import annotations

import argparse
import copy
import io
import json
import os
import platform
import re
import subprocess
import sys
import unittest
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
import lifecycle_development_v2_2 as lifecycle  # noqa: E402
import toolsandbox_model_pilot_runner_validation_v2_1 as engine  # noqa: E402
from failure_memory.proper_v2.v2_3 import ActionEffectClass  # noqa: E402
from toolsandbox_five_condition_runner_adapter_v2_3 import (  # noqa: E402
    FIFTH_CONDITION, ExecutionAwareTrajectoryGuard, PublicEffectRegistry,
)

CONFIG = ROOT / "configs" / "proper_v2_3" / "guarded_runner_validation_v2_3.json"
CONDITIONS = [
    "tfidf_rank1_memory",
    "proper_v2_1_memory",
    "proper_lifecycle_prompt_only",
    "proper_lifecycle_replan_controller",
    FIFTH_CONDITION,
]


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


def safe_host_token() -> str:
    token = re.sub(r"[^a-zA-Z0-9_-]+", "-", platform.node()).strip("-").lower()
    return token or "unnamed-host"


def verify_preconditions(config: Mapping[str, Any], expected_revision: str) -> dict[str, Any]:
    policy = config["remote_validation"]
    if os.environ.get("PROPER_V2_3_EXECUTION_ROLE") != policy["execution_role"]:
        raise RuntimeError("guarded-runner execution role is missing")
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "-1":
        raise RuntimeError("CPU-only CUDA guard is missing")
    if sys.version_info.major != 3 or sys.version_info.minor not in policy["allowed_python_minors"]:
        raise RuntimeError(f"unsupported Python version: {platform.python_version()}")
    if not re.fullmatch(r"[0-9a-f]{40}", expected_revision):
        raise RuntimeError("expected project revision must be a full Git commit")
    head = git("rev-parse", "HEAD")
    if head != expected_revision:
        raise RuntimeError(f"project revision mismatch: expected {expected_revision}, got {head}")
    if git("status", "--porcelain", "--untracked-files=no"):
        raise RuntimeError("tracked project worktree must be clean")
    for item in config["frozen_inputs"]:
        path = ROOT / str(item["path"])
        observed = engine.sha256_file(path)
        if observed != str(item["sha256"]):
            raise RuntimeError(f"frozen input mismatch: {item['path']}")
    return {
        "execution_role": policy["execution_role"],
        "project_revision": head,
        "tracked_worktree_clean": True,
        "cuda_visible_devices": "-1",
        "python_version": platform.python_version(),
    }


def prepare_engine_files(
    config: Mapping[str, Any], run_directory: Path,
) -> tuple[Path, Path, dict[str, Any]]:
    source_item = config["source_prepared_manifest"]
    source_path = ROOT / str(source_item["path"])
    if engine.sha256_file(source_path) != str(source_item["sha256"]):
        raise RuntimeError("passed five-condition manifest hash mismatch")
    manifest = load_json(source_path)
    if manifest.get("status") != "passed":
        raise RuntimeError("source five-condition preparation did not pass")
    manifest["agent_budget"] = copy.deepcopy(config["agent_budget"])
    manifest["cohort"]["condition_order"] = list(CONDITIONS)
    manifest["ready_for_runner_implementation"] = True
    manifest["identities"] = {
        "source_prepared_manifest_sha256": str(source_item["sha256"]),
    }
    manifest["identities"]["prepared_payload_sha256"] = engine.sha256_text(
        engine.canonical(manifest)
    )
    manifest_path = run_directory / "engine_manifest.json"
    write_json(manifest_path, manifest)

    base = load_json(ROOT / str(config["engine_base_config"]["path"]))
    base["prepared_manifest"] = {
        "path": manifest_path.relative_to(ROOT).as_posix(),
        "sha256": engine.sha256_file(manifest_path),
        "prepared_payload_sha256": manifest["identities"]["prepared_payload_sha256"],
    }
    base["expected"].update({"pair_count": 12, "condition_count": 60})
    base["output"] = {"path": (run_directory / "unused.json").relative_to(ROOT).as_posix()}
    base["boundary"].update({
        "scripted_decisions_only": True,
        "model_loaded": False,
        "model_outputs_read": False,
        "gpu_run_authorized": False,
        "existing_model_exposed_pairs": True,
    })
    engine_config_path = run_directory / "engine_config.json"
    write_json(engine_config_path, base)
    return manifest_path, engine_config_path, manifest


class ScriptedGuardedProvider:
    """Exercise the adapter without loading or querying a model."""

    def __init__(self, config: Mapping[str, Any], engine_config: Mapping[str, Any]) -> None:
        self.config = config
        self.engine_config = engine_config
        stage = load_json(ROOT / str(config["lifecycle_config"]["path"]))
        self.lifecycle_policy = continuation.lifecycle_policy(stage)
        registry_payload = load_json(ROOT / str(config["effect_registry"]["path"]))
        self.registry = PublicEffectRegistry(registry_payload)
        self.guards: dict[str, ExecutionAwareTrajectoryGuard] = {}
        self.source_records: dict[str, Mapping[str, Any]] = {}
        self.injected_history_lengths: set[tuple[str, int]] = set()

    def _base(self, kwargs: Mapping[str, Any]) -> dict[str, Any]:
        return engine.synthetic_decision(
            record=kwargs["record"], condition=str(kwargs["condition"]),
            branch_history=kwargs["branch_history"],
            prefix_history=kwargs["prefix_history"], config=self.engine_config,
        )

    @staticmethod
    def _metadata(index: int, proposed: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "request_id": f"scripted-adapter-attempt-{index}",
            "request_sha256": engine.sha256_text(engine.canonical(proposed)),
            "raw_text": engine.canonical(proposed),
            "valid_json_decision": True,
            "parse_error": None,
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

    def decide(self, **kwargs: Any) -> dict[str, Any]:
        if kwargs["condition"] != FIFTH_CONDITION:
            return self._base(kwargs)
        record = kwargs["record"]
        history = kwargs["branch_history"]
        pair_id = str(record["pair_id"])
        self.source_records[pair_id] = record
        memory, lifecycle_state = lifecycle.state_from_history(
            record, history, self.lifecycle_policy,
        )
        guard = self.guards.get(pair_id)
        if guard is None:
            guard = ExecutionAwareTrajectoryGuard(
                record=record, config=self.config["method_config"],
                effect_registry=self.registry, prefix_history=kwargs["prefix_history"],
            )
            self.guards[pair_id] = guard
        guard.sync_history(history, lifecycle_state)
        attempts: list[dict[str, Any]] = []
        blocked: list[dict[str, Any]] = []
        key = (pair_id, len(history))
        repeat_probe_required = bool(history) and (
            len(history) == 1
            or self.registry.contract(str(history[-1]["tool_name"])).effect_class
            == ActionEffectClass.NON_IDEMPOTENT_SIDE_EFFECT
        )
        if repeat_probe_required and key not in self.injected_history_lengths:
            self.injected_history_lengths.add(key)
            repeated = {
                "kind": "tool", "tool_name": history[-1]["tool_name"],
                "arguments": copy.deepcopy(history[-1]["arguments"]),
            }
            attempt = self._metadata(1, repeated)
            review = guard.review(repeated, valid=True)
            attempts.append(attempt)
            if review["decision"] is not None and not review["decision"].decision_allowed:
                blocked_item = {
                    "proposed_decision": repeated,
                    "review": review["decision"].to_mapping(),
                }
                blocked.append(blocked_item)
                guard.runtime.blocked_attempts.append(copy.deepcopy(blocked_item))
            else:
                raise RuntimeError("scripted successful duplicate was not blocked")
        proposed = self._base(kwargs)
        model = self._metadata(len(attempts) + 1, proposed)
        review = guard.review(proposed, valid=True)
        attempts.append(model)
        decision = review["decision"]
        if proposed["kind"] == "tool" and (decision is None or not decision.decision_allowed):
            proposed = {
                "kind": "stop", "reason_code": guard.runtime.state.stop_reason or "controller_stop",
                "message": "The scripted controller stopped safely.",
            }
        proposed["_model"] = model
        proposed["_model_attempts"] = attempts
        proposed["_controller"] = {
            "guard_applied": True,
            "blocked_attempts": blocked,
            "execution_guard_snapshot": guard.snapshot(),
        }
        return proposed

    def finalize_records(self, records: list[dict[str, Any]]) -> None:
        for record in records:
            pair_id = str(record["pair_id"])
            condition = record["conditions"][FIFTH_CONDITION]
            source = self.source_records[pair_id]
            _, state = lifecycle.state_from_history(
                source, condition["tool_history"], self.lifecycle_policy,
            )
            snapshot, safety = self.guards[pair_id].finalize_summary(
                history=condition["tool_history"], lifecycle_state=state,
            )
            condition["action_execution_guard"] = snapshot
            condition["execution_safety"] = safety


def run_tests(config: Mapping[str, Any]) -> dict[str, Any]:
    policy = config["test_policy"]
    suite = unittest.TestSuite()
    for pattern in policy["patterns"]:
        suite.addTests(unittest.defaultTestLoader.discover(
            str(ROOT / "tests"), pattern=pattern, top_level_dir=str(ROOT / "tests")
        ))
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    count_matches = result.testsRun == int(policy["expected_test_count"])
    return {
        "passed": result.wasSuccessful() and count_matches,
        "tests_run": result.testsRun,
        "expected_test_count": policy["expected_test_count"],
        "test_count_matches_contract": count_matches,
        "failures": len(result.failures), "errors": len(result.errors),
        "skipped": len(result.skipped), "runner_output": stream.getvalue(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-project-revision", required=True)
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()
    config_path = args.config.resolve()
    config = load_json(config_path)
    preconditions = verify_preconditions(config, args.expected_project_revision)
    started = datetime.now(timezone.utc)
    run_id = f"{started.strftime('%Y%m%dT%H%M%SZ')}-{safe_host_token()}-{args.expected_project_revision[:12]}"
    run_directory = ROOT / str(config["output"]["root"]) / run_id
    run_directory.mkdir(parents=True, exist_ok=False)
    manifest_path, engine_config_path, _ = prepare_engine_files(config, run_directory)
    engine_config = load_json(engine_config_path)
    provider = ScriptedGuardedProvider(config, engine_config)
    result = engine.run_validation(engine_config_path, decision_provider=provider)
    provider.finalize_records(result["records"])
    fifth = [item["conditions"][FIFTH_CONDITION] for item in result["records"]]
    fifth_entries = [
        entry
        for item in fifth
        for entry in item["action_execution_guard"]["ledger"]["entries"]
    ]
    successful_repeat_blocks = []
    for item in fifth:
        entries = item["action_execution_guard"]["ledger"]["entries"]
        by_id = {entry["entry_id"]: entry for entry in entries}
        successful_repeat_blocks.extend(
            entry
            for entry in entries
            if not entry["decision_allowed"]
            and any(
                by_id[related]["status"] == "succeeded"
                for related in entry["related_entry_ids"]
            )
        )
    adapter_source = (V23 / "toolsandbox_five_condition_runner_adapter_v2_3.py").read_text(encoding="utf-8")
    provider_source = (V23 / "toolsandbox_five_condition_provider_v2_3.py").read_text(encoding="utf-8")
    forbidden = config["method_source_forbidden_tokens"]
    checks = {
        "base_engine_validation_passed": result["summary"]["runner_validation_passed"],
        "all_five_conditions_executed": result["summary"]["condition_count"] == 60,
        "all_fifth_ledgers_present": len(fifth) == 12,
        "all_allowed_executions_resolved": all(
            item["execution_safety"]["all_allowed_executions_resolved"] for item in fifth
        ),
        "successful_duplicates_were_exercised_and_blocked": bool(
            successful_repeat_blocks
        ),
        "non_idempotent_duplicate_was_exercised_and_blocked": any(
            not entry["decision_allowed"]
            and entry["effect_contract"]["effect_class"]
            == ActionEffectClass.NON_IDEMPOTENT_SIDE_EFFECT.value
            for entry in fifth_entries
        ),
        "no_duplicate_non_idempotent_execution": all(
            item["execution_safety"]["duplicate_non_idempotent_execution_count"] == 0
            for item in fifth
        ),
        "complete_trajectory_includes_prefix": all(
            item["execution_safety"]["prefix_entry_count"]
            == len(record["prefix_history"])
            for item, record in zip(fifth, result["records"])
        ),
        "method_sources_have_no_forbidden_branch_tokens": not any(
            token in adapter_source or token in provider_source for token in forbidden
        ),
    }
    tests = run_tests(config)
    passed = all(checks.values()) and tests["passed"]
    result["guarded_runner_validation"] = {
        "checks": checks, "passed": passed,
        "scripted_duplicate_proposal_count": sum(
            item["execution_safety"]["blocked_proposal_count"] for item in fifth
        ),
        "model_request_count": 0, "gpu_used": False,
    }
    result_path = run_directory / "scripted_engine_result.json"
    write_json(result_path, result)
    envelope = {
        "schema_version": 1,
        "run_kind": "proper_v2_3_guarded_runner_cpu_validation",
        "run_id": run_id, "passed": passed,
        "preconditions": preconditions,
        "identities": {
            "config_sha256": engine.sha256_file(config_path),
            "engine_manifest_sha256": engine.sha256_file(manifest_path),
            "engine_config_sha256": engine.sha256_file(engine_config_path),
            "adapter_sha256": engine.sha256_file(V23 / "toolsandbox_five_condition_runner_adapter_v2_3.py"),
            "provider_sha256": engine.sha256_file(V23 / "toolsandbox_five_condition_provider_v2_3.py"),
            "result_sha256": engine.sha256_file(result_path),
        },
        "checks": checks, "tests": tests,
        "boundary": {
            "scripted_decisions_only": True, "model_loaded": False,
            "model_outputs_read": False, "gpu_used": False,
            "development_model_run_authorized": False,
            "confirmatory_claim_authorized": False,
            "heldout_claim_authorized": False,
        },
        "next_gate": (
            "freeze_guarded_model_runner_and_gpu_development_command"
            if passed else "stop_and_preserve_guarded_runner_failure"
        ),
    }
    import jsonschema
    schema = load_json(
        ROOT / "schemas/proper_v2_3/guarded_runner_validation.schema.json"
    )
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(envelope)
    write_json(run_directory / "guarded_runner_validation.json", envelope)
    print(json.dumps({
        "passed": passed, "tests_run": tests["tests_run"],
        "blocked_duplicate_proposals": result["guarded_runner_validation"]["scripted_duplicate_proposal_count"],
        "model_loaded": False, "gpu_used": False,
        "output": str(run_directory / "guarded_runner_validation.json"),
    }, ensure_ascii=False, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
