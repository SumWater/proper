"""Replay frozen tau3 scripted evidence through execution-state continuation."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from failure_memory.proper_v2 import RecoveryOperation  # noqa: E402
from failure_memory.proper_v2.v2_2 import LifecycleStatus, PlanningMode  # noqa: E402
from failure_memory.proper_v2.v2_3 import (  # noqa: E402
    ActionPurpose,
    BudgetState,
    ContinuationDisposition,
    ControllerState,
    EvidenceSource,
    ExecutionStatus,
    ObservableProgressEvidence,
    SubgoalContract,
    execution_ledger_from_mapping,
    initial_progress_state,
    route_observable_progress,
)

DEFAULT_CONFIG = (
    ROOT / "configs/proper_v2_3/tau3_execution_state_continuation_screen_v2_3.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "outputs/proper_v2_3/tau3_execution_state_continuation_screen/screen.json"
)


def _load(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"expected object in {path}")
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _operation(effect_class: str) -> RecoveryOperation:
    return {
        "read_only": RecoveryOperation.INVOKE_PREREQUISITE,
        "idempotent_state_setting": RecoveryOperation.REPAIR_ARGUMENTS,
        "non_idempotent_side_effect": RecoveryOperation.RETRY_SAME_ACTION,
    }[effect_class]


def _controller_from_pair(pair: Mapping[str, Any], ledger: Any) -> ControllerState:
    recovery_entries = [
        item for item in ledger.entries if item.purpose == ActionPurpose.RECOVERY
    ]
    if len(recovery_entries) != 1:
        raise ValueError("each frozen branch pair must contain one recovery proposal")
    return ControllerState(
        phase=recovery_entries[0].phase,
        selected_memory_experience_id=f"memory::{pair['failure_family']}",
        memory_operation=_operation(str(pair["effect_class"])),
        memory_action_identity=recovery_entries[0].normalized_identity,
        lifecycle_status=LifecycleStatus.CONSUMED,
        planning_mode=PlanningMode.ORDINARY_TASK_PLANNING,
        budgets=BudgetState(**pair["final_budgets"]),
        transition_index=0,
    )


def _continuation_entries(ledger: Any, expected_count: int) -> list[Any]:
    entries = [
        item
        for item in ledger.entries
        if item.purpose == ActionPurpose.ORDINARY_TASK
        and item.status == ExecutionStatus.SUCCEEDED
        and any(
            evidence.code == "scripted_public_result:continuation_observed"
            for evidence in item.evidence
        )
    ]
    if len(entries) != expected_count:
        raise ValueError("frozen branch does not contain the expected continuation evidence")
    return entries


def replay_pair(pair: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, Any]:
    ledger = execution_ledger_from_mapping(pair["ledger"])
    controller = _controller_from_pair(pair, ledger)
    contracts = tuple(
        SubgoalContract(
            item["subgoal_id"],
            item["description"],
            (item["success_evidence_code"],),
        )
        for item in config["progress_contract"]["subgoals"]
    )
    progress = initial_progress_state(
        trajectory_id=ledger.trajectory_id, subgoals=contracts
    )
    entries = _continuation_entries(
        ledger, config["input"]["expected_continuation_actions_per_pair"]
    )
    decisions = []
    for index, entry in enumerate(entries):
        evidence_step = max(record.observed_at_step for record in entry.evidence)
        decision = route_observable_progress(
            progress_state=progress,
            controller_state=controller,
            ledger=ledger,
            evidence=ObservableProgressEvidence(
                EvidenceSource.TOOL_RESULT,
                ("scripted_public_result:continuation_observed",),
                evidence_step,
                completed_subgoal_ids=(contracts[index].subgoal_id,),
                task_complete=index == len(entries) - 1,
            ),
            stall_threshold=config["progress_contract"]["stall_threshold"],
        )
        decisions.append(decision)
        progress = decision.progress_state
        controller = decision.controller_state
    unresolved = [
        item.entry_id
        for item in ledger.entries
        if item.decision_allowed
        and item.status in {ExecutionStatus.EXECUTED, ExecutionStatus.OUTCOME_UNKNOWN}
    ]
    return {
        "pair_id": pair["pair_id"],
        "domain": pair["domain"],
        "effect_class": pair["effect_class"],
        "input_lifecycle_consumed": pair["lifecycle_after_recovery"] == "consumed",
        "input_exact_repeat_blocked": pair["exact_repeat_blocked"],
        "guarded_native_execution_count": pair["guarded_native_execution_count"],
        "unresolved_allowed_ledger_entry_ids": unresolved,
        "first_disposition": decisions[0].disposition.value,
        "final_disposition": decisions[-1].disposition.value,
        "final_reason": decisions[-1].reason_code,
        "final_progress_state": decisions[-1].progress_state.to_mapping(),
        "passed": (
            decisions[0].disposition == ContinuationDisposition.CONTINUE
            and decisions[-1].disposition == ContinuationDisposition.STOP
            and decisions[-1].reason_code
            == config["progress_contract"]["required_final_reason"]
            and not unresolved
        ),
    }


def run_screen(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = _load(config_path)
    branch_path = ROOT / config["input"]["branch_screen_path"]
    branch = _load(branch_path)
    pairs = [replay_pair(item, config) for item in branch["pairs"]]
    effects = collections.Counter(item["effect_class"] for item in pairs)
    expected = config["input"]
    checks = {
        "frozen_branch_hash_matches": _sha256(branch_path)
        == expected["branch_screen_sha256"],
        "all_input_branch_checks_passed": branch["passed"]
        and all(branch["checks"].values()),
        "pair_count_matches": len(pairs) == expected["expected_pair_count"],
        "effect_balance_matches": all(
            effects[name] == expected["expected_per_effect_class"]
            for name in (
                "read_only",
                "idempotent_state_setting",
                "non_idempotent_side_effect",
            )
        ),
        "all_ledgers_resolved": all(
            not item["unresolved_allowed_ledger_entry_ids"] for item in pairs
        ),
        "all_progress_handoffs_pass": all(item["passed"] for item in pairs),
        "all_input_repeats_blocked": all(
            item["input_exact_repeat_blocked"] for item in pairs
        ),
        "non_idempotent_native_execution_once": all(
            item["guarded_native_execution_count"] == 1
            for item in pairs
            if item["effect_class"] == "non_idempotent_side_effect"
        ),
        "no_model_or_gpu_authority": all(
            config["boundary"][key] is False
            for key in (
                "model_loaded",
                "model_outputs_read",
                "gpu_used",
                "confirmatory_claim_authorized",
            )
        ),
    }
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_3_tau3_execution_state_continuation_screen",
        "config_sha256": _sha256(config_path),
        "input_branch_screen_sha256": _sha256(branch_path),
        "checks": checks,
        "passed": all(checks.values()),
        "summary": {
            "pair_count": len(pairs),
            "effect_counts": dict(sorted(effects.items())),
            "scripted_progress_completion_count": sum(item["passed"] for item in pairs),
            "new_heldout_target_capacity": 0,
        },
        "pairs": pairs,
        "model_loaded": False,
        "model_outputs_read": False,
        "gpu_used": False,
        "development_model_protocol_design_authorized": all(checks.values()),
        "development_model_run_authorized": False,
        "confirmatory_run_authorized": False,
        "next_gate": (
            "freeze_tau3_continuation_development_protocol"
            if all(checks.values())
            else "stop_and_preserve_negative_screen"
        ),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = run_screen(args.config)
    output = args.output.resolve()
    allowed = (ROOT / "outputs/proper_v2_3").resolve()
    if not output.is_relative_to(allowed):
        raise ValueError("output must remain under outputs/proper_v2_3")
    if output.exists():
        raise FileExistsError(f"refusing to overwrite continuation screen: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "passed": result["passed"],
                "pair_count": result["summary"]["pair_count"],
                "gpu_used": False,
                "model_loaded": False,
                "next_gate": result["next_gate"],
                "output": str(output),
            },
            sort_keys=True,
        )
    )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
