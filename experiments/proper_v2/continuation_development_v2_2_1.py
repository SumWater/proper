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
    / "toolsandbox_continuation_development_v2_2_1.yaml"
)
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments" / "proper_v2"))

import lifecycle_development_v2_2 as lifecycle_helper  # noqa: E402
from failure_memory.proper_v2.contracts import ProposedAction  # noqa: E402
from failure_memory.proper_v2.v2_2 import (  # noqa: E402
    LifecyclePolicy,
    LifecycleStatus,
)
from failure_memory.proper_v2.v2_2_1 import (  # noqa: E402
    ContinuationPolicy,
    ReviewDisposition,
    initial_continuation_state,
    record_completed_action,
    review_decision,
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
    if config.get("status") != (
        "scripted_continuation_development_before_v2_2_1_model_outputs"
    ):
        raise RuntimeError("v2.2.1 continuation config status is invalid")
    boundary = config["boundary"]
    if (
        not boundary["scripted_decisions_only"]
        or not boundary["existing_model_exposed_pairs"]
        or boundary["model_loaded"]
        or boundary["new_model_outputs_read"]
        or boundary["gpu_run_authorized"]
        or boundary["confirmatory_claim_authorized"]
    ):
        raise RuntimeError("v2.2.1 continuation boundary is invalid")
    for item in config["frozen_inputs"].values():
        target = ROOT / str(item["path"])
        observed = sha256_file(target)
        if observed != str(item["sha256"]):
            raise RuntimeError(
                f"frozen continuation input mismatch: {target}; "
                f"expected={item['sha256']} observed={observed}"
            )
    return config


def load_manifest(config: Mapping[str, Any]) -> dict[str, Any]:
    item = config["frozen_inputs"]["prepared_manifest"]
    return json.loads((ROOT / str(item["path"])).read_text(encoding="utf-8"))


def lifecycle_policy(config: Mapping[str, Any]) -> LifecyclePolicy:
    return LifecyclePolicy.from_mapping(config["lifecycle_policy"])


def continuation_policy(config: Mapping[str, Any]) -> ContinuationPolicy:
    return ContinuationPolicy.from_mapping(config["continuation_policy"])


def continuation_state_from_history(
    record: Mapping[str, Any],
    history: list[Mapping[str, Any]],
    *,
    lifecycle_runtime_policy: LifecyclePolicy,
    continuation_runtime_policy: ContinuationPolicy,
):
    memory, lifecycle_state = lifecycle_helper.state_from_history(
        record,
        history,
        lifecycle_runtime_policy,
    )
    state = initial_continuation_state(
        lifecycle_state,
        continuation_runtime_policy,
    )
    if (
        lifecycle_state.status == LifecycleStatus.CONSUMED
        and memory.proposed_action is not None
    ):
        for item in history:
            action = ProposedAction(
                tool_name=str(item["tool_name"]),
                argument_template=dict(item["arguments"]),
            )
            if (
                action == memory.proposed_action
                and item.get("exception") is None
            ):
                state = record_completed_action(
                    state,
                    lifecycle_state=lifecycle_state,
                    action=action,
                    success_evidence=(
                        "action_succeeded",
                        "tool_result:success",
                    ),
                )
                break
    return memory, lifecycle_state, state


def static_validation(config_path: Path = CONFIG) -> dict[str, Any]:
    config = load_config(config_path)
    manifest = load_manifest(config)
    life_policy = lifecycle_policy(config)
    cont_policy = continuation_policy(config)
    records = []
    for record in manifest["records"]:
        memory, lifecycle_state, state = continuation_state_from_history(
            record,
            [],
            lifecycle_runtime_policy=life_policy,
            continuation_runtime_policy=cont_policy,
        )
        if memory.proposed_action is None:
            review = review_decision(
                state,
                lifecycle_state,
                memory,
                {
                    "kind": "tool",
                    "tool_name": str(record["branch_action"]["tool_name"]),
                    "arguments": dict(record["branch_action"]["arguments"]),
                },
                cont_policy,
            )
            records.append(
                {
                    "pair_id": record["pair_id"],
                    "decision_phase": record["decision_phase"],
                    "initial_lifecycle_status": lifecycle_state.status.value,
                    "safe_stop": (
                        review.disposition == ReviewDisposition.STOP
                        and not review.decision_allowed
                    ),
                    "repeat_replan": False,
                    "repeat_executed": False,
                    "replan_handoff": False,
                    "review": review.to_mapping(),
                }
            )
            continue

        successful_history = [
            {
                "tool_name": memory.proposed_action.tool_name,
                "arguments": dict(memory.proposed_action.argument_template),
                "result": None,
                "exception": None,
            }
        ]
        memory, lifecycle_state, state = continuation_state_from_history(
            record,
            successful_history,
            lifecycle_runtime_policy=life_policy,
            continuation_runtime_policy=cont_policy,
        )
        repeat = {
            "kind": "tool",
            "tool_name": memory.proposed_action.tool_name,
            "arguments": dict(memory.proposed_action.argument_template),
        }
        repeat_review = review_decision(
            state,
            lifecycle_state,
            memory,
            repeat,
            cont_policy,
        )
        handoff_review = review_decision(
            repeat_review.state,
            lifecycle_state,
            memory,
            {
                "kind": "stop",
                "reason_code": "scripted_ordinary_planning_handoff",
                "message": "",
            },
            cont_policy,
        )
        records.append(
            {
                "pair_id": record["pair_id"],
                "decision_phase": record["decision_phase"],
                "initial_lifecycle_status": lifecycle_state.status.value,
                "safe_stop": False,
                "repeat_replan": (
                    repeat_review.disposition == ReviewDisposition.REPLAN
                    and not repeat_review.decision_allowed
                ),
                "repeat_executed": False,
                "replan_handoff": (
                    handoff_review.disposition == ReviewDisposition.ALLOW
                    and handoff_review.decision_allowed
                ),
                "repeat_review": repeat_review.to_mapping(),
                "handoff_review": handoff_review.to_mapping(),
            }
        )
    post = [item for item in records if item["decision_phase"] == "post_failure"]
    pre = [item for item in records if item["decision_phase"] == "pre_action"]
    summary = {
        "pair_count": len(records),
        "post_failure_consumed_count": sum(
            item["initial_lifecycle_status"] == "consumed" for item in post
        ),
        "pre_action_safe_stop_count": sum(item["safe_stop"] for item in pre),
        "post_failure_repeat_replan_count": sum(
            item["repeat_replan"] for item in post
        ),
        "post_failure_repeat_execution_count": sum(
            item["repeat_executed"] for item in post
        ),
        "post_failure_replan_handoff_count": sum(
            item["replan_handoff"] for item in post
        ),
    }
    expected = config["scripted_expectations"]
    checks = {
        key: int(summary[key]) == int(expected[key])
        for key in expected
    }
    checks["pair_count"] = summary["pair_count"] == int(
        config["development_cohort"]["pair_count"]
    )
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_2_1_static_continuation_development",
        "identities": {
            "config_sha256": sha256_file(config_path),
            "prepared_manifest_sha256": config["frozen_inputs"][
                "prepared_manifest"
            ]["sha256"],
        },
        "summary": summary,
        "checks": checks,
        "passed": all(checks.values()),
        "records": records,
        "boundary": dict(config["boundary"]),
        "interpretation_limits": {
            "scripted_state_machine_only": True,
            "existing_pairs_are_development_only": True,
            "model_continuation_not_tested": True,
            "final_task_completion_not_tested": True,
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
        description="Validate the v2.2.1 continuation state machine locally."
    )
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()
    config = load_config(args.config)
    result = static_validation(args.config)
    output = write_result(result, config)
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2, sort_keys=True))
    print(f"OUTPUT={output}")
    status = "PASS" if result["passed"] else "STOP"
    print(f"RESULT={status}_PROPER_V2_2_1_STATIC_CONTINUATION")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
