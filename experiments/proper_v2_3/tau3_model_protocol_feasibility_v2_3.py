"""CPU-only feasibility gate before freezing a tau3 model protocol.

This audit never imports the tau3 runtime, executes a task, loads a model, or
constructs a branch from evaluator actions.  It checks whether the already
frozen development candidates have the public branch artifacts required for a
fair same-start model comparison.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "configs/proper_v2_3/tau3_model_protocol_feasibility_v2_3.json"
DEFAULT_OUTPUT = ROOT / "outputs/proper_v2_3/tau3_model_protocol_feasibility/audit.json"


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_revision(directory: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(directory), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _tasks(domain: str, source: Path) -> dict[str, dict[str, Any]]:
    path = source / f"data/tau2/domains/{domain}/tasks.json"
    raw = _load(path)
    items = raw["tasks"] if isinstance(raw, dict) else raw
    return {str(item["id"]): item for item in items}


def _visible_scalar_arguments(action: dict[str, Any], task: dict[str, Any]) -> bool:
    """Conservative task-start provenance check for scalar arguments only."""

    visible = json.dumps(task["user_scenario"], ensure_ascii=False).casefold()
    values: list[str] = []
    for value in (action.get("arguments") or {}).values():
        if isinstance(value, (str, int, float, bool)):
            values.append(str(value).casefold())
        else:
            return False
    return bool(values) and all(value in visible for value in values)


def run_audit(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = _load(config_path)
    source = ROOT / config["source"]["directory"]
    candidate_path = ROOT / config["source"]["candidate_config"]
    candidate_config = _load(candidate_path)
    artifacts = {
        item["pair_id"]: item for item in config["available_branch_artifacts"]
    }
    task_cache: dict[str, dict[str, dict[str, Any]]] = {}
    pair_results = []
    for candidate in candidate_config["candidates"]:
        domain = candidate["domain"]
        task_cache.setdefault(domain, _tasks(domain, source))
        task = task_cache[domain].get(str(candidate["source_task_id"]))
        action = None
        if task is not None:
            actions = task["evaluation_criteria"]["actions"]
            if 0 <= candidate["action_index"] < len(actions):
                action = actions[candidate["action_index"]]
        mapped = action is not None and action["name"] == candidate["guarded_action_name"]
        start_visible = bool(
            mapped
            and candidate["phase"] == "pre_action"
            and _visible_scalar_arguments(action, task)
        )
        artifact = artifacts.get(candidate["pair_id"])
        post_failure_ready = bool(
            mapped
            and candidate["phase"] == "post_failure"
            and artifact
            and artifact.get("public_message_history")
            and artifact.get("environment_initialization")
            and artifact.get("public_failure_receipt")
            and artifact.get("identical_start_replay_proof")
        )
        model_ready = start_visible if candidate["phase"] == "pre_action" else post_failure_ready
        pair_results.append(
            {
                "pair_id": candidate["pair_id"],
                "domain": domain,
                "phase": candidate["phase"],
                "effect_class": candidate["effect_class"],
                "source_action_mapping_valid": mapped,
                "task_start_arguments_publicly_visible": start_visible,
                "frozen_public_branch_artifact_present": artifact is not None,
                "post_failure_branch_ready": post_failure_ready,
                "model_ready": model_ready,
                "reason": (
                    "public_task_start_is_sufficient"
                    if model_ready and candidate["phase"] == "pre_action"
                    else "frozen_public_post_failure_branch_is_sufficient"
                    if model_ready
                    else "missing_frozen_public_post_failure_branch"
                    if candidate["phase"] == "post_failure"
                    else "task_start_argument_provenance_not_public"
                ),
            }
        )

    ready = [item for item in pair_results if item["model_ready"]]
    ready_effects = Counter(item["effect_class"] for item in ready)
    phase_counts = Counter(item["phase"] for item in pair_results)
    ready_phase_counts = Counter(item["phase"] for item in ready)
    all_mapped = all(item["source_action_mapping_valid"] for item in pair_results)
    expected_count = config["source"]["expected_candidate_count"]
    source_revision = _git_revision(source)
    protocol_ready = (
        len(pair_results) == expected_count
        and len(ready) == expected_count
        and len(ready_effects) == 3
        and ready_phase_counts["post_failure"] > 0
    )
    checks = {
        "source_revision_matches": source_revision == config["source"]["revision"],
        "candidate_count_matches": len(pair_results) == expected_count,
        "all_candidate_actions_map_to_source": all_mapped,
        "no_model_branch_artifact_was_invented": len(artifacts) == 0,
        "audit_observes_expected_readiness_gap": len(ready) == 4
        and ready_phase_counts["pre_action"] == 4
        and ready_phase_counts["post_failure"] == 0,
        "protocol_correctly_stops_before_model_runner": not protocol_ready,
    }
    result = {
        "schema_version": 1,
        "run_kind": "proper_v2_3_tau3_model_protocol_feasibility_audit",
        "config_sha256": _sha256(config_path),
        "candidate_config_sha256": _sha256(candidate_path),
        "source_revision": source_revision,
        "checks": checks,
        "audit_passed": all(checks.values()),
        "protocol_ready": protocol_ready,
        "summary": {
            "candidate_count": len(pair_results),
            "source_action_mapping_count": sum(
                item["source_action_mapping_valid"] for item in pair_results
            ),
            "model_ready_count": len(ready),
            "phase_counts": dict(sorted(phase_counts.items())),
            "model_ready_phase_counts": {
                phase: ready_phase_counts.get(phase, 0) for phase in sorted(phase_counts)
            },
            "model_ready_effect_counts": dict(sorted(ready_effects.items())),
            "new_heldout_target_capacity": 0,
        },
        "pairs": pair_results,
        "method_inputs_include_evaluator_metadata": False,
        "task_executed": False,
        "model_loaded": False,
        "model_outputs_read": False,
        "gpu_used": False,
        "model_protocol_freeze_authorized": protocol_ready,
        "model_runner_implementation_authorized": protocol_ready,
        "development_model_run_authorized": False,
        "confirmatory_run_authorized": False,
        "disposition": "freeze_model_protocol" if protocol_ready else "stop_before_model_protocol",
        "next_gate": (
            "freeze_tau3_development_model_protocol"
            if protocol_ready
            else "design_public_branch_capture_without_model_exposure"
        ),
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = run_audit(args.config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(
        (json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
            "utf-8"
        )
    )
    print(json.dumps(result["summary"], ensure_ascii=False, sort_keys=True))
    return 0 if result["audit_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
