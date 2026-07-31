from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
CONFIG = (
    ROOT
    / "configs"
    / "proper_v2"
    / "toolsandbox_unconsumed_capacity_v2_2.yaml"
)
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments" / "proper_v2"))

import toolsandbox_selector_capacity as base  # noqa: E402
import toolsandbox_selector_capacity_v2 as behavioral  # noqa: E402
from failure_memory.proper_v2 import (  # noqa: E402
    DecisionPhase,
    ObservableRecoveryState,
    RecoveryOperation,
    RetrySafety,
    RetrySafetyAssessment,
    select_memory,
)
from failure_memory.proper_v2.v2_2 import (  # noqa: E402
    LifecycleMemorySpec,
    LifecycleObservation,
    LifecyclePolicy,
    LifecycleStatus,
    guard_decision,
    start_lifecycle,
)
from failure_memory.retrieval import (  # noqa: E402
    Experience,
    FailureQuery,
    SourceBlindTfidfRetriever,
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("status") != (
        "frozen_unconsumed_cpu_capacity_before_any_target_model_outputs"
    ):
        raise RuntimeError("unconsumed capacity config status is invalid")
    boundary = config["boundary"]
    if (
        not boundary["cpu_only"]
        or boundary["target_model_outputs_read"]
        or boundary["target_scenarios_played"]
        or boundary["model_loaded"]
        or boundary["gpu_run_authorized"]
        or boundary["confirmatory_run_authorized"]
    ):
        raise RuntimeError("unconsumed capacity audit must remain CPU-only")
    for item in config["frozen_inputs"].values():
        target = ROOT / str(item["path"])
        observed = sha256_file(target)
        if observed != str(item["sha256"]):
            raise RuntimeError(
                f"frozen input mismatch: {target}; "
                f"expected={item['sha256']} observed={observed}"
            )
    return config


def load_json_input(
    config: Mapping[str, Any],
    name: str,
) -> dict[str, Any]:
    item = config["frozen_inputs"][name]
    return json.loads(
        (ROOT / str(item["path"])).read_text(encoding="utf-8")
    )


def intervention_signature(card: Any) -> str:
    proposed = (
        {
            "tool_name": card.proposed_action.tool_name,
            "arguments": dict(card.proposed_action.argument_template),
        }
        if card.proposed_action is not None
        else None
    )
    return json.dumps(
        {
            "recovery_operation": card.recovery_operation.value,
            "proposed_action": proposed,
            "continuation_policy": card.continuation_policy.value,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def memory_bank(
    config: Mapping[str, Any],
) -> tuple[
    list[Experience],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
]:
    behavioral_config = load_json_input(config, "behavioral_capacity_config")
    action_payload = load_json_input(config, "action_memory_preparation")
    legacy_manifest = load_json_input(config, "legacy_selection_manifest")
    action_definitions = {
        str(item["experience_id"]): dict(item)
        for item in action_payload["memory_cards"]
    }
    action_experiences = [
        Experience(
            experience_id=experience_id,
            source_instance_id=str(card["source_family"]),
            natural_text=str(card["natural_text"]),
            policy=base.policy_for_retrieval(
                RecoveryOperation(str(card["recovery_operation"]))
            ),
            provenance="toolsandbox_scripted_action_memory",
        )
        for experience_id, card in sorted(action_definitions.items())
    ]
    stop_config = dict(behavioral_config)
    stop_config["toolsandbox_memory_cards"] = behavioral_config[
        "stop_memory_cards"
    ]
    stop_experiences, stop_definitions = base.configured_toolsandbox_memories(
        stop_config
    )
    legacy_experiences, legacy_definitions = base.configured_legacy_memories(
        behavioral_config,
        legacy_manifest,
    )
    experiences = action_experiences + stop_experiences + legacy_experiences
    if len(experiences) != int(config["retrieval"]["top_k"]):
        raise RuntimeError("frozen memory-bank count does not match top_k")
    return (
        experiences,
        action_definitions,
        stop_definitions,
        legacy_definitions,
    )


def target_state(
    declaration: Mapping[str, Any],
) -> ObservableRecoveryState:
    return ObservableRecoveryState(
        phase=DecisionPhase.PRE_ACTION,
        instruction=str(declaration["instruction"]),
        action=None,
        error_code=None,
        evidence_codes=tuple(declaration["evidence_codes"]),
        failed_argument_paths=(),
        missing_fields=(),
        public_schema_fields=(),
        public_required_fields=(),
        available_tools=tuple(declaration["available_tools"]),
        available_capabilities=(
            "request_information",
            "stop_and_report",
        ),
        satisfied_facts=(),
        violated_facts=(
            f"capability:{declaration['unavailable_required_capability']}",
        ),
        repeated_same_call_count=0,
        retry_safety=RetrySafetyAssessment(RetrySafety.UNKNOWN),
    )


def prepare(config_path: Path = CONFIG) -> dict[str, Any]:
    config = load_config(config_path)
    inventory = load_json_input(config, "dynamic_inventory")
    prior_capacity = load_json_input(config, "phase_aware_capacity")
    prepared = load_json_input(config, "v2_1_prepared_manifest")
    inventory_by_name = {
        str(item["name"]): item for item in inventory["records"]
    }
    exposed = {str(item["scenario_name"]) for item in prepared["records"]}
    source_families = set(
        prior_capacity["source_target_split"]["source_families"]
    )
    target_family = str(config["target_family"])
    declarations = config["target_declarations"]
    experiences, action_defs, stop_defs, legacy_defs = memory_bank(config)
    retriever = SourceBlindTfidfRetriever(experiences)
    policy = LifecyclePolicy(
        maximum_application_attempts=2,
        consumed_memory_weight=0.0,
        require_success_evidence=True,
        stop_on_success_trigger_conflict=True,
    )

    records = []
    for declaration in declarations:
        name = str(declaration["scenario_name"])
        metadata = inventory_by_name[name]
        if str(metadata["semantic_family"]) != target_family:
            raise RuntimeError(f"target family mismatch: {name}")
        if sorted(metadata["tools"]) != sorted(declaration["available_tools"]):
            raise RuntimeError(f"public tool declaration mismatch: {name}")
        target = target_state(declaration)
        query = " ".join(
            [
                str(declaration["instruction"]),
                "Unavailable required capability",
                str(declaration["unavailable_required_capability"]),
                "Evidence",
                " ".join(declaration["evidence_codes"]),
            ]
        )
        ranked = retriever.retrieve(
            FailureQuery(
                instance_id=name,
                natural_text=query,
                provenance="toolsandbox_unconsumed_target",
            ),
            top_k=int(config["retrieval"]["top_k"]),
        )
        cards = []
        for item in ranked:
            experience_id = item.experience.experience_id
            kwargs = {"rank": item.rank, "score": round(item.score, 12)}
            if experience_id in action_defs:
                card = base.toolsandbox_card(
                    action_defs[experience_id],
                    **kwargs,
                )
            elif experience_id in stop_defs:
                card = base.toolsandbox_card(
                    stop_defs[experience_id],
                    **kwargs,
                )
            else:
                card = base.legacy_card(
                    legacy_defs[experience_id],
                    **kwargs,
                )
            cards.append(card)
        decision = select_memory(
            target,
            cards,
            minimum_extraction_confidence=float(
                config["selector"]["minimum_extraction_confidence"]
            ),
        )
        rank1 = min(cards, key=lambda item: item.original_rank)
        selected = next(
            item
            for item in cards
            if item.experience_id == decision.selected_experience_id
        )
        spec = LifecycleMemorySpec.from_mapping(
            selected.to_mapping(),
            fallback_trigger_evidence=target.evidence_codes,
        )
        lifecycle_state = start_lifecycle(
            spec,
            LifecycleObservation(
                phase=DecisionPhase.PRE_ACTION,
                active_trigger_evidence=target.evidence_codes,
                evidence_codes=target.evidence_codes,
            ),
            policy,
        )
        unsafe_allowed, guard_reason = guard_decision(
            lifecycle_state,
            spec,
            {
                "kind": "tool",
                "tool_name": "search_contacts",
                "arguments": {"phone_number": "+12453344098"},
            },
        )
        behavior_distinct = (
            intervention_signature(rank1) != intervention_signature(selected)
        )
        specific_target_evidence = set(target.evidence_codes) - {
            "failure_state:insufficient_information"
        }
        selected_specific_trigger_match = bool(
            specific_target_evidence & set(selected.trigger_evidence)
        )
        records.append(
            {
                "scenario_name": name,
                "semantic_family": target_family,
                "instruction": declaration["instruction"],
                "v2_1_model_exposed": name in exposed,
                "exact_source_family_overlap": target_family in source_families,
                "within_domain_sibling_family": True,
                "rank1_experience_id": rank1.experience_id,
                "rank1_operation": rank1.recovery_operation.value,
                "selected_experience_id": selected.experience_id,
                "selected_operation": selected.recovery_operation.value,
                "selection_changed": decision.selection_changed,
                "behaviorally_distinct": behavior_distinct,
                "selected_policy_safe": (
                    selected.recovery_operation
                    == RecoveryOperation.STOP_AND_REPORT
                ),
                "selected_specific_trigger_match": (
                    selected_specific_trigger_match
                ),
                "lifecycle_initial_status": lifecycle_state.status.value,
                "lifecycle_tool_call_blocked": not unsafe_allowed,
                "lifecycle_guard_reason": guard_reason,
                "selection_decision": decision.to_mapping(),
            }
        )

    behaviorally_distinct = sum(
        item["behaviorally_distinct"] for item in records
    )
    independent_families = len(
        {item["semantic_family"] for item in records}
    )
    all_selector_safe = all(item["selected_policy_safe"] for item in records)
    all_specific_trigger_match = all(
        item["selected_specific_trigger_match"] for item in records
    )
    all_lifecycle_safe = all(
        item["lifecycle_tool_call_blocked"] for item in records
    )
    no_exposure = all(not item["v2_1_model_exposed"] for item in records)
    no_exact_overlap = all(
        not item["exact_source_family_overlap"] for item in records
    )
    gate = config["capacity_gate"]
    audit_checks = {
        "exact_target_count": len(records)
        == int(gate["exact_target_count"]),
        "all_selected_policies_safe": (
            all_selector_safe
            if gate["require_all_selected_policies_safe"]
            else True
        ),
        "all_selected_specific_trigger_match": (
            all_specific_trigger_match
            if gate["require_all_selected_specific_trigger_match"]
            else True
        ),
        "all_lifecycle_guards_safe": (
            all_lifecycle_safe
            if gate["require_all_lifecycle_guards_safe"]
            else True
        ),
        "no_v2_1_model_exposure": (
            no_exposure if gate["require_no_v2_1_model_exposure"] else True
        ),
        "no_exact_source_family_overlap": (
            no_exact_overlap
            if gate["require_no_exact_source_family_overlap"]
            else True
        ),
    }
    audit_completed = all(
        audit_checks[key]
        for key in (
            "exact_target_count",
            "no_v2_1_model_exposure",
            "no_exact_source_family_overlap",
        )
    )
    development_ready = (
        all(audit_checks.values())
        and behaviorally_distinct
        >= int(
            gate[
                "minimum_behaviorally_distinct_pairs_for_development_holdout"
            ]
        )
    )
    confirmation_capacity = (
        development_ready
        and independent_families
        >= int(
            gate[
                "minimum_independent_semantic_families_for_confirmation"
            ]
        )
        and not config["boundary"]["within_domain_sibling_family"]
    )
    summary = {
        "target_count": len(records),
        "behaviorally_distinct_pair_count": behaviorally_distinct,
        "independent_semantic_family_count": independent_families,
        "selected_operation_counts": dict(
            sorted(
                Counter(
                    item["selected_operation"] for item in records
                ).items()
            )
        ),
        "all_selected_policies_safe": all_selector_safe,
        "all_selected_specific_trigger_match": all_specific_trigger_match,
        "all_lifecycle_guards_safe": all_lifecycle_safe,
        "development_model_output_holdout_ready": development_ready,
        "confirmatory_capacity_ready": confirmation_capacity,
    }
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_2_unconsumed_target_cpu_capacity",
        "identities": {
            "config_sha256": sha256_file(config_path),
            "producer_source_sha256": sha256_file(Path(__file__)),
            "protocol_sha256": sha256_file(
                ROOT / str(config["protocol"])
            ),
            "frozen_input_sha256": {
                name: str(item["sha256"])
                for name, item in config["frozen_inputs"].items()
            },
        },
        "audit_checks": audit_checks,
        "audit_passed": audit_completed,
        "summary": summary,
        "records": records,
        "next_action": (
            "freeze_development_model_output_holdout_protocol"
            if development_ready
            else (
                "do_not_run_model_preservation_only_and_specific_trigger_mismatch"
            )
        ),
        "boundary": dict(config["boundary"]),
        "interpretation_limits": {
            "selector_capacity_is_not_model_effect": True,
            "lifecycle_guard_capacity_is_not_model_effect": True,
            "final_task_completion_not_tested": True,
            "safety_outcome_not_tested_with_model": True,
            "cost_not_tested": True,
            "within_domain_sibling_transfer_only": True,
            "confirmatory_run_not_authorized": True,
        },
    }


def write_result(
    result: Mapping[str, Any],
    config: Mapping[str, Any],
) -> Path:
    output = ROOT / str(config["output"]["path"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit the two unconsumed v2.2 targets on CPU."
    )
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()
    config = load_config(args.config)
    result = prepare(args.config)
    output = write_result(result, config)
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2, sort_keys=True))
    print(f"NEXT_ACTION={result['next_action']}")
    print(f"OUTPUT={output}")
    status = "PASS" if result["audit_passed"] else "STOP"
    print(f"RESULT={status}_PROPER_V2_2_UNCONSUMED_CPU_CAPACITY")
    return 0 if result["audit_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
