from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
CONFIG = (
    ROOT
    / "configs"
    / "proper_v2"
    / "toolsandbox_lifecycle_development_v2_2.yaml"
)
sys.path.insert(0, str(ROOT / "src"))

from failure_memory.proper_v2.contracts import (  # noqa: E402
    DecisionPhase,
    ProposedAction,
)
from failure_memory.proper_v2.v2_2 import (  # noqa: E402
    LifecycleMemorySpec,
    LifecycleObservation,
    LifecyclePolicy,
    LifecycleState,
    LifecycleStatus,
    advance_lifecycle,
    guard_decision,
    lifecycle_prompt_payload,
    start_lifecycle,
)


def canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if (
        config.get("status")
        != "scripted_lifecycle_development_before_v2_2_model_outputs"
    ):
        raise RuntimeError("v2.2 lifecycle development config status is invalid")
    boundary = config["boundary"]
    if (
        not boundary["scripted_decisions_only"]
        or boundary["model_loaded"]
        or boundary["model_outputs_read"]
        or boundary["gpu_run_authorized"]
    ):
        raise RuntimeError("scripted lifecycle validation cannot use model outputs")
    for item in config["frozen_inputs"].values():
        target = ROOT / str(item["path"])
        if sha256_file(target) != str(item["sha256"]):
            raise RuntimeError(f"frozen v2.2 input hash mismatch: {target}")
    return config


def load_manifest(config: Mapping[str, Any]) -> dict[str, Any]:
    item = config["frozen_inputs"]["v2_1_prepared_manifest"]
    return json.loads((ROOT / str(item["path"])).read_text(encoding="utf-8"))


def lifecycle_policy(config: Mapping[str, Any]) -> LifecyclePolicy:
    lifecycle = config["lifecycle"]
    return LifecyclePolicy(
        maximum_application_attempts=int(
            lifecycle["maximum_application_attempts"]
        ),
        consumed_memory_weight=float(lifecycle["consumed_memory_weight"]),
        require_success_evidence=bool(
            lifecycle["require_success_evidence"]
        ),
        stop_on_success_trigger_conflict=bool(
            lifecycle["stop_on_success_trigger_conflict"]
        ),
    )


def observable_state(record: Mapping[str, Any]) -> dict[str, Any]:
    messages = record["conditions"]["proper_v2_1_memory"]["initial_request"][
        "messages"
    ]
    marker = "OBSERVABLE_RECOVERY_STATE="
    for message in messages:
        for line in str(message["content"]).splitlines():
            if line.startswith(marker):
                payload = json.loads(line[len(marker) :])
                if not isinstance(payload, dict):
                    raise RuntimeError("observable recovery state must be an object")
                return payload
    raise RuntimeError("prepared request lacks OBSERVABLE_RECOVERY_STATE")


def memory_spec(record: Mapping[str, Any]) -> LifecycleMemorySpec:
    state = observable_state(record)
    memory = record["conditions"]["proper_v2_1_memory"]["memory"]
    return LifecycleMemorySpec.from_mapping(
        memory,
        fallback_trigger_evidence=tuple(state.get("evidence_codes", ())),
    )


def initial_observation(record: Mapping[str, Any]) -> LifecycleObservation:
    state = observable_state(record)
    return LifecycleObservation(
        phase=DecisionPhase(str(record["decision_phase"])),
        active_trigger_evidence=tuple(state.get("evidence_codes", ())),
        evidence_codes=tuple(state.get("evidence_codes", ())),
    )


def state_from_history(
    record: Mapping[str, Any],
    history: list[Mapping[str, Any]],
    policy: LifecyclePolicy,
) -> tuple[LifecycleMemorySpec, LifecycleState]:
    memory = memory_spec(record)
    state = start_lifecycle(memory, initial_observation(record), policy)
    for item in history:
        action = ProposedAction(
            tool_name=str(item["tool_name"]),
            argument_template=dict(item["arguments"]),
        )
        state = advance_lifecycle(
            state,
            memory,
            LifecycleObservation(
                phase=state.phase,
                active_trigger_evidence=(
                    memory.trigger_evidence
                    if item.get("exception") is not None
                    else ()
                ),
                action=action,
                action_succeeded=item.get("exception") is None,
                evidence_codes=(
                    ("tool_exception",)
                    if item.get("exception") is not None
                    else ("tool_result:success",)
                ),
            ),
            policy,
        )
    return memory, state


def static_validation(config_path: Path = CONFIG) -> dict[str, Any]:
    config = load_config(config_path)
    manifest = load_manifest(config)
    policy = lifecycle_policy(config)
    records = []
    for record in manifest["records"]:
        memory, state = state_from_history(record, [], policy)
        if memory.proposed_action is None:
            unsafe_allowed, unsafe_reason = guard_decision(
                state,
                memory,
                {
                    "kind": "tool",
                    "tool_name": record["branch_action"]["tool_name"],
                    "arguments": record["branch_action"]["arguments"],
                },
            )
            state = advance_lifecycle(
                state,
                memory,
                LifecycleObservation(
                    phase=state.phase,
                    agent_stop_reason="scripted_safe_stop",
                ),
                policy,
            )
            ordinary_handoff = False
            repeat_blocked = not unsafe_allowed
            guard_reason = unsafe_reason
        else:
            state = advance_lifecycle(
                state,
                memory,
                LifecycleObservation(
                    phase=state.phase,
                    action=memory.proposed_action,
                    action_succeeded=True,
                    evidence_codes=("tool_result:success",),
                ),
                policy,
            )
            repeat_allowed, guard_reason = guard_decision(
                state,
                memory,
                {
                    "kind": "tool",
                    "tool_name": memory.proposed_action.tool_name,
                    "arguments": dict(
                        memory.proposed_action.argument_template
                    ),
                },
            )
            repeat_blocked = not repeat_allowed
            ordinary_handoff = (
                lifecycle_prompt_payload(state, memory)["memory"] is None
            )
        records.append(
            {
                "pair_id": record["pair_id"],
                "decision_phase": record["decision_phase"],
                "memory_experience_id": memory.experience_id,
                "final_lifecycle": state.to_mapping(),
                "ordinary_planning_handoff": ordinary_handoff,
                "memory_action_repeat_blocked": repeat_blocked,
                "guard_reason": guard_reason,
            }
        )

    post = [item for item in records if item["decision_phase"] == "post_failure"]
    pre = [item for item in records if item["decision_phase"] == "pre_action"]
    summary = {
        "pair_count": len(records),
        "post_failure_pair_count": len(post),
        "pre_action_pair_count": len(pre),
        "post_failure_consumed_count": sum(
            item["final_lifecycle"]["status"] == LifecycleStatus.CONSUMED.value
            for item in post
        ),
        "pre_action_stopped_count": sum(
            item["final_lifecycle"]["status"] == LifecycleStatus.STOPPED.value
            for item in pre
        ),
        "ordinary_planning_handoff_count": sum(
            item["ordinary_planning_handoff"] for item in post
        ),
        "memory_action_repeat_blocked_count": sum(
            item["memory_action_repeat_blocked"] for item in records
        ),
    }
    expected = config["scripted_expectations"]
    checks = {
        "pair_count": summary["pair_count"]
        == int(config["development_cohort"]["pair_count"]),
        "phase_counts": (
            summary["post_failure_pair_count"]
            == int(config["development_cohort"]["post_failure_pair_count"])
            and summary["pre_action_pair_count"]
            == int(config["development_cohort"]["pre_action_pair_count"])
        ),
        "post_failure_consumed": summary["post_failure_consumed_count"]
        == int(expected["post_failure_consumed_count"]),
        "pre_action_stopped": summary["pre_action_stopped_count"]
        == int(expected["pre_action_stopped_count"]),
        "ordinary_planning_handoff": summary[
            "ordinary_planning_handoff_count"
        ]
        == int(expected["ordinary_planning_handoff_count"]),
        "all_memory_action_repeats_blocked": summary[
            "memory_action_repeat_blocked_count"
        ]
        == len(records),
    }
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_2_static_lifecycle_development_validation",
        "identities": {
            "config_sha256": sha256_file(config_path),
            "prepared_manifest_sha256": config["frozen_inputs"][
                "v2_1_prepared_manifest"
            ]["sha256"],
        },
        "summary": summary,
        "checks": checks,
        "passed": all(checks.values()),
        "records": records,
        "boundary": dict(config["boundary"]),
        "interpretation_limits": {
            "v2_1_pairs_are_development_only": True,
            "selector_first_step_not_retested": True,
            "no_model_behavior_tested": True,
            "final_task_completion_not_tested": True,
            "safety_guards_tested": True,
            "cost_effect_not_tested": True,
        },
    }


def write_result(
    result: Mapping[str, Any],
    config: Mapping[str, Any],
) -> Path:
    output = ROOT / str(config["outputs"]["static_validation"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate PROPER v2.2 lifecycle without ToolSandbox or a model."
    )
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()
    config = load_config(args.config)
    result = static_validation(args.config)
    output = write_result(result, config)
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2, sort_keys=True))
    print(f"OUTPUT={output}")
    status = "PASS" if result["passed"] else "STOP"
    print(f"RESULT={status}_PROPER_V2_2_STATIC_LIFECYCLE_VALIDATION")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
