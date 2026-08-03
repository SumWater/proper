"""One-shot remote tau3 public-branch acquisition runner.

Importing this module does not import tau3, torch, transformers, or a task
runtime. The executable path remains guarded by exact revision, inventory,
source, environment, and CUDA preflight checks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.failure_memory.proper_v2.v2_3.acquisition_runtime import (
    AttemptSpec,
    EnvironmentExecution,
    JsonlSubprocessWorker,
    run_attempt,
)
from src.failure_memory.proper_v2.v2_3.acquisition_runtime_protocol import canonical_sha256
from src.failure_memory.proper_v2.v2_3.model_inventory import inventory_regular_files
from src.failure_memory.proper_v2.v2_3.tau3_acquisition_runtime_adapter import (
    build_pinned_tau_environment,
)


PROTOCOL_CONFIG = ROOT / "configs/proper_v2_3/acquisition_one_shot_runner_protocol_v2_3.json"
RUNTIME_CONFIG = ROOT / "configs/proper_v2_3/acquisition_runtime_protocol_v2_3.json"
CANDIDATE_CONFIG = ROOT / "configs/proper_v2_3/tau3_branch_screen_v2_3.yaml"
PROMPT_CONFIG = ROOT / "configs/proper_v2_3/local_tau_participant_prompts_v2_3.json"
EFFECT_CONFIG = ROOT / "configs/proper_v2_3/tau3_acquisition_action_effects_v2_3.json"
IMPLEMENTATION_CONFIG = ROOT / "configs/proper_v2_3/acquisition_one_shot_runner_implementation_v2_3.json"


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str, directory: Path = ROOT) -> str:
    return subprocess.run(
        ["git", "-c", "core.fileMode=false", "-C", str(directory), *args],
        check=True, capture_output=True, text=True, encoding="utf-8",
    ).stdout.strip()


def atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes((json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    temporary.replace(path)


def execution_manifest(source: Path) -> dict[str, Any]:
    files: list[Path] = []
    for relative in (
        "src/tau2/domains/airline", "src/tau2/domains/retail",
        "src/tau2/environment", "src/tau2/utils",
    ):
        files.extend(sorted((source / relative).glob("*.py")))
    for domain in ("airline", "retail"):
        base = source / "data/tau2/domains" / domain
        files.extend(base / name for name in ("db.json", "tasks.json", "split_tasks.json", "policy.md"))
    records = [
        {"path": path.relative_to(source).as_posix(), "sha256": sha256(path), "bytes": path.stat().st_size}
        for path in sorted(files)
    ]
    return {
        "file_count": len(records), "bytes": sum(item["bytes"] for item in records),
        "sha256": canonical_sha256(records),
    }


def load_and_verify_tasks(runtime_config: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    expected = {item["pair_id"]: item for item in runtime_config["task_hashes"]}
    by_domain: dict[str, dict[str, Any]] = {}
    for domain in {item["domain"] for item in expected.values()}:
        raw = json.loads((ROOT / f"external/tau2-bench/data/tau2/domains/{domain}/tasks.json").read_text(encoding="utf-8"))
        items = raw["tasks"] if isinstance(raw, dict) else raw
        by_domain[domain] = {str(item["id"]): item for item in items}
    verified: dict[str, dict[str, Any]] = {}
    for pair_id, item in expected.items():
        task = by_domain[item["domain"]][str(item["source_task_id"])]
        observed = {
            "full_task_sha256": canonical_sha256(task),
            "user_scenario_sha256": canonical_sha256(task["user_scenario"]),
            "initial_state_sha256": canonical_sha256(task.get("initial_state")),
            "evaluator_only_sha256": canonical_sha256(task["evaluation_criteria"]),
        }
        if any(observed[key] != item[key] for key in observed):
            raise RuntimeError(f"frozen task component hash mismatch: {pair_id}")
        verified[pair_id] = {"domain": item["domain"], "task": task}
    return verified


def action_registries(effect_config: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    return {
        domain: {item["action_name"]: item["effect_class"] for item in rows}
        for domain, rows in effect_config["contracts"].items()
    }


def candidate_records(candidate_config: Mapping[str, Any], order: Sequence[str]) -> list[dict[str, Any]]:
    by_id = {item["pair_id"]: item for item in candidate_config["candidates"]}
    if set(by_id) != set(order) or len(by_id) != len(order):
        raise RuntimeError("candidate partition differs from frozen capture order")
    return [by_id[pair_id] for pair_id in order]


def evaluate_preflight_observation(observed: Mapping[str, Any]) -> dict[str, bool]:
    return {
        "project_revision_matches": bool(observed.get("project_revision_matches")),
        "tracked_worktree_clean": bool(observed.get("tracked_worktree_clean")),
        "output_directory_absent": bool(observed.get("output_directory_absent")),
        "frozen_input_hashes_match": bool(observed.get("frozen_input_hashes_match")),
        "tau_revision_matches": bool(observed.get("tau_revision_matches")),
        "tau_execution_manifest_matches": bool(observed.get("tau_execution_manifest_matches")),
        "domain_inputs_match": bool(observed.get("domain_inputs_match")),
        "task_components_match": bool(observed.get("task_components_match")),
        "model_inventory_matches": bool(observed.get("model_inventory_matches")),
        "project_python_matches": bool(observed.get("project_python_matches")),
        "worker_dependencies_available": bool(observed.get("worker_dependencies_available")),
        "cuda_device_zero_available": bool(observed.get("cuda_device_zero_available")),
    }


def collect_real_preflight(
    expected_revision: str,
    output_directory: Path,
    *,
    output_was_absent: bool | None = None,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    protocol = load_object(PROTOCOL_CONFIG)
    runtime = load_object(RUNTIME_CONFIG)
    remote = protocol["remote_runtime"]
    source = ROOT / remote["tau_source"]
    head = git("rev-parse", "HEAD")
    frozen_hashes = all(sha256(ROOT / item["path"]) == item["sha256"] for item in protocol["frozen_inputs"])
    manifest = execution_manifest(source)
    source_lock = load_object(CANDIDATE_CONFIG)["source_lock"]
    domain_hashes = runtime["source_runtime"]["domains"]
    domain_ok = all(
        sha256(source / f"data/tau2/domains/{domain}/{filename}") == values[key]
        for domain, values in domain_hashes.items()
        for filename, key in (("tasks.json", "tasks_file_sha256"), ("policy.md", "policy_sha256"), ("db.json", "database_sha256"))
    ) and sha256(source / "data/tau2/user_simulator/simulation_guidelines.md") == runtime["source_runtime"]["user_simulation_guidelines_sha256"]
    tasks: dict[str, dict[str, Any]] = {}
    task_ok = False
    try:
        tasks = load_and_verify_tasks(runtime)
        task_ok = True
    except (KeyError, OSError, ValueError, RuntimeError):
        task_ok = False
    model = runtime["model"]
    inventory = inventory_regular_files(Path(model["path"]), chunk_bytes=8388608)
    model_ok = inventory["manifest_sha256"] == model["content_manifest_sha256"] and inventory["file_count"] == model["inventory_file_count"] and inventory["total_bytes"] == model["inventory_total_bytes"]
    expected_project_python = (ROOT / remote["project_python"]).resolve()
    worker_probe = subprocess.run(
        [remote["worker_python"], "-c", "import json,torch,transformers,accelerate; print(json.dumps({'cuda':torch.cuda.is_available(),'count':torch.cuda.device_count()}))"],
        cwd=ROOT, env={**os.environ, "CUDA_VISIBLE_DEVICES": remote["cuda_visible_devices"]},
        capture_output=True, text=True, check=False,
    )
    try:
        probe = json.loads(worker_probe.stdout.strip()) if worker_probe.returncode == 0 else {}
    except json.JSONDecodeError:
        probe = {}
    observed = {
        "project_revision_matches": bool(re.fullmatch(r"[0-9a-f]{40}", expected_revision)) and head == expected_revision,
        "tracked_worktree_clean": git("status", "--porcelain", "--untracked-files=no") == "",
        "output_directory_absent": (
            not output_directory.exists()
            if output_was_absent is None
            else output_was_absent
        ),
        "frozen_input_hashes_match": frozen_hashes,
        "tau_revision_matches": git("rev-parse", "HEAD", directory=source) == remote["tau_revision"],
        "tau_execution_manifest_matches": manifest == {"file_count":source_lock["execution_manifest_file_count"],"bytes":source_lock["execution_manifest_bytes"],"sha256":source_lock["execution_manifest_sha256"]},
        "domain_inputs_match": domain_ok,
        "task_components_match": task_ok,
        "model_inventory_matches": model_ok,
        "project_python_matches": Path(sys.executable).resolve() == expected_project_python and sys.version_info[:2] in {(3, 11), (3, 12)},
        "worker_dependencies_available": worker_probe.returncode == 0,
        "cuda_device_zero_available": probe.get("cuda") is True and int(probe.get("count", 0)) >= 1,
        "project_revision": head,
        "tau_manifest": manifest,
        "model_inventory_manifest_sha256": inventory.get("manifest_sha256"),
        "worker_probe_returncode": worker_probe.returncode,
    }
    return observed, tasks


class TimedWorker:
    def __init__(self, worker: JsonlSubprocessWorker, started: float) -> None:
        self.worker = worker
        self.started = started
        self.startup_to_first_response_seconds = 0.0

    def complete(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        response = self.worker.complete(request)
        if self.startup_to_first_response_seconds == 0.0:
            self.startup_to_first_response_seconds = time.monotonic() - self.started
        return response


def zero_cost(preflight_seconds: float = 0.0) -> dict[str, Any]:
    return {
        "agent_request_count":0,"agent_prompt_tokens":0,"agent_completion_tokens":0,
        "user_request_count":0,"user_prompt_tokens":0,"user_completion_tokens":0,
        "native_tool_execution_count":0,"tool_error_count":0,"orchestrator_step_count":0,
        "preflight_wall_clock_seconds":preflight_seconds,"model_startup_to_first_response_seconds":0.0,"run_wall_clock_seconds":0.0,
    }


def aggregate_cost(attempts: Sequence[Mapping[str, Any]], *, preflight_seconds: float, startup_seconds: float, run_seconds: float) -> dict[str, Any]:
    cost = zero_cost(preflight_seconds)
    cost["model_startup_to_first_response_seconds"] = startup_seconds
    cost["run_wall_clock_seconds"] = run_seconds
    for attempt in attempts:
        state = attempt["public_state"]
        agent, user = state["agent_usage"], state["user_usage"]
        cost["agent_request_count"] += agent["requests"]
        cost["agent_prompt_tokens"] += agent["prompt_tokens"]
        cost["agent_completion_tokens"] += agent["completion_tokens"]
        cost["user_request_count"] += user["requests"]
        cost["user_prompt_tokens"] += user["prompt_tokens"]
        cost["user_completion_tokens"] += user["completion_tokens"]
        cost["native_tool_execution_count"] += state["native_tool_execution_count"]
        cost["tool_error_count"] += state["tool_errors"]
        cost["orchestrator_step_count"] += state["steps"]
    return cost


def duplicate_non_idempotent_count(attempts: Sequence[Mapping[str, Any]]) -> int:
    duplicates = 0
    for attempt in attempts:
        seen: set[str] = set()
        for entry in attempt["public_state"]["ledger"]:
            if entry["effect_class"] == "non_idempotent_side_effect" and entry["executed"] and entry["outcome"] in {"succeeded", "unknown"}:
                if entry["signature"] in seen:
                    duplicates += 1
                seen.add(entry["signature"])
    return duplicates


def build_envelope(*, project_revision: str, attempts: Sequence[Mapping[str, Any]], artifact_records: Sequence[Mapping[str, Any]], status: str, stop_reason: str | None, preflight_seconds: float, startup_seconds: float, run_seconds: float, model_response_observed: bool = False, task_attempt_started: bool = False) -> dict[str, Any]:
    protocol = load_object(PROTOCOL_CONFIG)
    captured = sum(item["public_state"]["status"] == "captured" for item in attempts)
    post_captured = sum(item["phase"] == "post_failure" and item["public_state"]["status"] == "captured" for item in attempts)
    duplicates = duplicate_non_idempotent_count(attempts)
    checks = {
        "all_twelve_attempts_written": len(attempts) == 12,
        "all_twelve_branches_captured": captured == 12,
        "all_eight_post_failure_branches_captured": post_captured == 8,
        "zero_duplicate_non_idempotent_execution": duplicates == 0,
        "all_artifact_hashes_present": len(artifact_records) == len(attempts) and all(re.fullmatch(r"[0-9a-f]{64}", str(item["sha256"])) for item in artifact_records),
    }
    passed = all(checks.values()) and status == "completed"
    return {
        "schema_version":2,"run_kind":"proper_v2_3_tau3_qwen_public_branch_acquisition",
        "implementation_config_sha256":sha256(IMPLEMENTATION_CONFIG),"project_revision":project_revision,
        "tau_revision":protocol["remote_runtime"]["tau_revision"],"model_manifest_sha256":protocol["remote_runtime"]["model_manifest_sha256"],
        "status":status,"stop_reason":stop_reason,"smoke_pair_id":protocol["execution"]["smoke_pair_id"],
        "smoke_passed":bool(attempts and attempts[0]["evaluator_pair_id"] == protocol["execution"]["smoke_pair_id"] and attempts[0]["public_state"]["status"] == "captured"),
        "capture_attempt_count":len(attempts),"captured_branch_count":captured,"post_failure_captured_count":post_captured,
        "duplicate_non_idempotent_execution_count":duplicates,"attempt_artifacts":list(artifact_records),
        "cost":aggregate_cost(attempts,preflight_seconds=preflight_seconds,startup_seconds=startup_seconds,run_seconds=run_seconds),
        "checks":checks,"boundary":{"development_only":True,"heldout":False,"confirmatory":False,"external_api_called":False,"protocol_tuned_after_output":False,"resumed_or_rerun":False,"model_loaded":model_response_observed,"model_outputs_read":model_response_observed and any(record.get("raw_text") is not None for item in attempts for record in item.get("worker_records", [])),"task_executed":task_attempt_started,"gpu_used":model_response_observed},
        "next_gate":"freeze_tau3_five_condition_model_protocol" if passed else "stop_and_preserve_acquisition_result",
    }


def default_output(expected_revision: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    host = socket.gethostname().split(".")[0]
    return ROOT / "outputs/proper_v2_3/tau3_acquisition_remote" / f"{stamp}-{host}-{expected_revision[:12]}"


def execute_prepared_attempts(
    *,
    output_directory: Path,
    candidates: Sequence[Mapping[str, Any]],
    tasks: Mapping[str, Mapping[str, Any]],
    prompts: Mapping[str, Any],
    budgets: Mapping[str, Any],
    registries: Mapping[str, Mapping[str, str]],
    guidelines: str,
    worker: Any,
    environment_builder: Callable[..., tuple[Any, str, Sequence[Mapping[str, Any]]]],
    require_synthetic: bool,
    progress_callback: Callable[[Sequence[Mapping[str, Any]], Sequence[Mapping[str, Any]], str, str | None], None] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str, str | None]:
    attempts: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    status, stop_reason = "capture_stopped", None
    for ordinal, candidate in enumerate(candidates, 1):
        pair_id, domain = str(candidate["pair_id"]), str(candidate["domain"])
        environment, policy, tools = environment_builder(
            root=ROOT, domain=domain, raw_task=tasks[pair_id]["task"]
        )
        spec = AttemptSpec(
            attempt_ordinal=ordinal, evaluator_pair_id=pair_id,
            phase=str(candidate["phase"]),
            target_tool_name=str(candidate["guarded_action_name"]),
            target_effect_class=str(candidate["effect_class"]),
            public_policy=policy, public_tools=tools,
            simulation_guidelines=guidelines,
            private_user_scenario=tasks[pair_id]["task"]["user_scenario"],
            action_registry=registries[domain],
        )
        attempt = run_attempt(
            spec, prompt_config=prompts, budgets=budgets, worker=worker,
            environment=environment, require_synthetic=require_synthetic,
        )
        attempts.append(attempt)
        path = output_directory / "attempts" / f"attempt-{ordinal:02d}.json"
        atomic_json(path, attempt)
        state = attempt["public_state"]
        records.append({
            "pair_id":pair_id,"ordinal":ordinal,"phase":candidate["phase"],
            "effect_class":candidate["effect_class"],"capture_status":state["status"],
            "path":path.relative_to(output_directory).as_posix(),"sha256":sha256(path),
            "native_tool_execution_count":state["native_tool_execution_count"],
            "target_native_execution_count":state["target_native_execution_count"],
        })
        if state["status"] != "captured":
            status = "smoke_failed" if ordinal == 1 else "capture_stopped"
            stop_reason = state["failure_reason"] or state["status"]
        elif ordinal == len(candidates):
            status = "completed"
        if progress_callback is not None:
            progress_callback(attempts, records, status, stop_reason)
        if state["status"] != "captured":
            break
    return attempts, records, status, stop_reason


def run(expected_revision: str, output_directory: Path) -> dict[str, Any]:
    run_started = time.monotonic()
    preflight_started = time.monotonic()
    if output_directory.exists():
        raise FileExistsError(f"output directory already exists: {output_directory}")
    output_directory.mkdir(parents=True, exist_ok=False)
    preflight_interrupted = False
    try:
        observed, tasks = collect_real_preflight(
            expected_revision, output_directory, output_was_absent=True
        )
    except KeyboardInterrupt:
        observed, tasks = {"collection_error": "KeyboardInterrupt: preflight_interrupted"}, {}
        preflight_interrupted = True
    except Exception as exc:
        observed, tasks = {"collection_error": f"{type(exc).__name__}: {exc}"}, {}
    checks = evaluate_preflight_observation(observed)
    preflight_seconds = time.monotonic() - preflight_started
    atomic_json(output_directory / "preflight.json", {"observed":observed,"checks":checks,"passed":all(checks.values()),"model_loaded":False,"task_executed":False})
    if not all(checks.values()):
        envelope = build_envelope(project_revision=str(observed.get("project_revision") or "0" * 40),attempts=[],artifact_records=[],status="interrupted" if preflight_interrupted else "preflight_failed",stop_reason="preflight_interrupted" if preflight_interrupted else "preflight_failed",preflight_seconds=preflight_seconds,startup_seconds=0.0,run_seconds=time.monotonic()-run_started)
        atomic_json(output_directory / "result.json", envelope)
        return envelope

    protocol, runtime = load_object(PROTOCOL_CONFIG), load_object(RUNTIME_CONFIG)
    prompts, effects = load_object(PROMPT_CONFIG), load_object(EFFECT_CONFIG)
    candidates = candidate_records(load_object(CANDIDATE_CONFIG), protocol["execution"]["capture_order"])
    registries = action_registries(effects)
    guidelines = (ROOT / "external/tau2-bench/data/tau2/user_simulator/simulation_guidelines.md").read_text(encoding="utf-8")
    attempts: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    status, stop_reason = "capture_stopped", None
    worker_started = time.monotonic()
    worker_command = [protocol["remote_runtime"]["worker_python"], str(ROOT / protocol["remote_runtime"]["worker_script"]), "--model-path", protocol["remote_runtime"]["model_path"]]
    environment_vars = {**os.environ,"CUDA_VISIBLE_DEVICES":protocol["remote_runtime"]["cuda_visible_devices"],"TOKENIZERS_PARALLELISM":"false"}
    previous_environment = os.environ.copy()
    os.environ.update(environment_vars)
    timed_worker: TimedWorker | None = None
    try:
        with JsonlSubprocessWorker(worker_command,stderr_path=output_directory / "worker.stderr",timeout_seconds=float(protocol["model_worker"]["response_timeout_seconds"])) as raw_worker:
            timed_worker = TimedWorker(raw_worker, worker_started)
            def write_progress(
                current_attempts: Sequence[Mapping[str, Any]],
                current_records: Sequence[Mapping[str, Any]],
                current_status: str,
                current_reason: str | None,
            ) -> None:
                envelope = build_envelope(project_revision=expected_revision,attempts=current_attempts,artifact_records=current_records,status=current_status,stop_reason=current_reason,preflight_seconds=preflight_seconds,startup_seconds=timed_worker.startup_to_first_response_seconds,run_seconds=time.monotonic()-run_started,model_response_observed=timed_worker.startup_to_first_response_seconds > 0.0,task_attempt_started=bool(current_attempts))
                atomic_json(output_directory / "result.json", envelope)
            attempts, records, status, stop_reason = execute_prepared_attempts(
                output_directory=output_directory, candidates=candidates, tasks=tasks,
                prompts=prompts, budgets=runtime["budgets"], registries=registries,
                guidelines=guidelines, worker=timed_worker,
                environment_builder=build_pinned_tau_environment,
                require_synthetic=False, progress_callback=write_progress,
            )
    except KeyboardInterrupt:
        status, stop_reason = "interrupted", "keyboard_interrupt"
    except Exception as exc:
        status, stop_reason = ("smoke_failed" if not attempts else "capture_stopped"), f"runtime_exception:{type(exc).__name__}:{exc}"
    finally:
        os.environ.clear(); os.environ.update(previous_environment)
    envelope = build_envelope(project_revision=expected_revision,attempts=attempts,artifact_records=records,status=status,stop_reason=stop_reason,preflight_seconds=preflight_seconds,startup_seconds=timed_worker.startup_to_first_response_seconds if timed_worker else 0.0,run_seconds=time.monotonic()-run_started,model_response_observed=bool(timed_worker and timed_worker.startup_to_first_response_seconds > 0.0),task_attempt_started=bool(attempts))
    atomic_json(output_directory / "result.json", envelope)
    return envelope


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-project-revision", required=True)
    parser.add_argument("--output-directory", type=Path)
    args = parser.parse_args()
    output = args.output_directory or default_output(args.expected_project_revision)
    result = run(args.expected_project_revision, output)
    print(json.dumps({"output":str(output),"status":result["status"],"capture_attempt_count":result["capture_attempt_count"],"captured_branch_count":result["captured_branch_count"],"next_gate":result["next_gate"]},ensure_ascii=False,sort_keys=True))
    return 0 if result["status"] == "completed" and result["next_gate"] == "freeze_tau3_five_condition_model_protocol" else 1


if __name__ == "__main__":
    raise SystemExit(main())
