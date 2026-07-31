from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
CONFIG = (
    ROOT
    / "configs"
    / "proper_v2"
    / "toolsandbox_selector_capacity_v2.yaml"
)
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments" / "proper_v2"))

import toolsandbox_selector_capacity as base  # noqa: E402
from failure_memory.proper_v2 import MemoryPolicyCard, select_memory  # noqa: E402
from failure_memory.retrieval import (  # noqa: E402
    Experience,
    FailureQuery,
    SourceBlindTfidfRetriever,
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if (
        config.get("status")
        != "exploratory_cpu_behavioral_selector_capacity_before_model_outputs"
    ):
        raise RuntimeError("behavioral selector-capacity config has invalid status")
    return config


def resolve_and_verify(value: Mapping[str, Any]) -> Path:
    path = ROOT / str(value["path"])
    if sha256_file(path) != str(value["sha256"]):
        raise RuntimeError(f"input hash mismatch: {path}")
    return path


def action_memory_output(config: Mapping[str, Any]) -> tuple[Path, dict[str, Any]]:
    value = config["inputs"]["action_memory_preparation"]
    path = ROOT / str(value["path"])
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not payload["source_trajectories_passed"]:
        raise RuntimeError("action-memory source trajectories did not pass")
    if (
        payload["identities"]["config_sha256"]
        != str(value["producer_config_sha256"])
    ):
        raise RuntimeError("action-memory producer config mismatch")
    if len(payload["memory_cards"]) != int(value["expected_card_count"]):
        raise RuntimeError("unexpected action-memory card count")
    signatures = [
        str(card["behavior_signature"]) for card in payload["memory_cards"]
    ]
    if len(signatures) != len(set(signatures)):
        raise RuntimeError("action-memory output contains duplicate behavior")
    return path, payload


def canonical_action(card: MemoryPolicyCard) -> dict[str, Any] | None:
    if card.proposed_action is None:
        return None
    return {
        "tool_name": card.proposed_action.tool_name,
        "arguments": dict(card.proposed_action.argument_template),
    }


def intervention_signature(card: MemoryPolicyCard) -> str:
    """Action-level signature; stop reasons alone do not create an intervention."""
    return json.dumps(
        {
            "recovery_operation": card.recovery_operation.value,
            "proposed_action": canonical_action(card),
            "continuation_policy": card.continuation_policy.value,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def full_behavior_signature(card: MemoryPolicyCard) -> str:
    return json.dumps(
        {
            "intervention": json.loads(intervention_signature(card)),
            "stop_conditions": list(card.stop_conditions),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def summarize(
    records: list[dict[str, Any]], config: Mapping[str, Any]
) -> dict[str, Any]:
    identity_changed = [
        record for record in records if record["selection_changed"]
    ]
    operation_changed = [
        record for record in records if record["operation_changed"]
    ]
    intervention = [
        record for record in records if record["intervention_distinct"]
    ]
    full_behavior = [
        record for record in records if record["full_behavior_distinct"]
    ]
    families = {record["semantic_family"] for record in intervention}
    operations = {record["selected_operation"] for record in intervention}
    proposed_tools = {
        record["selected_proposed_action"]["tool_name"]
        for record in intervention
        if record["selected_proposed_action"] is not None
    }
    selected_counts = Counter(
        record["selected_experience_id"] for record in intervention
    )
    maximum = max(selected_counts.values(), default=0)
    maximum_share = maximum / len(intervention) if intervention else 0.0
    aligned = [
        record
        for record in records
        if record["selected_operation"] == record["target_policy_type"]
    ]
    stop_targets = [
        record
        for record in records
        if record["target_policy_type"] == "stop_and_report"
    ]
    stop_safe = [
        record
        for record in stop_targets
        if record["selected_operation"] == "stop_and_report"
    ]
    gate = config["capacity_gate"]
    checks = {
        "valid_target_capacity_met": len(records)
        >= int(gate["minimum_valid_targets"]),
        "intervention_distinct_capacity_met": len(intervention)
        >= int(gate["minimum_intervention_distinct_pairs"]),
        "intervention_semantic_family_diversity_met": len(families)
        >= int(gate["minimum_intervention_distinct_semantic_families"]),
        "intervention_operation_diversity_met": len(operations)
        >= int(gate["minimum_intervention_selected_operation_types"]),
        "intervention_proposed_tool_diversity_met": len(proposed_tools)
        >= int(gate["minimum_intervention_selected_proposed_tools"]),
        "intervention_selected_memory_diversity_met": len(selected_counts)
        >= int(gate["minimum_selected_memory_count_on_intervention_pairs"]),
        "intervention_memory_concentration_limit_met": maximum_share
        <= float(gate["maximum_single_selected_memory_share"]),
        "all_target_policy_alignment_met": (
            len(aligned) == len(records)
            if gate["require_all_target_policy_alignment"]
            else True
        ),
        "stop_target_safety_preservation_met": (
            len(stop_safe) == len(stop_targets)
            if gate["require_stop_target_safety_preservation"]
            else True
        ),
    }
    return {
        "valid_target_count": len(records),
        "identity_changed_count": len(identity_changed),
        "operation_changed_count": len(operation_changed),
        "intervention_distinct_count": len(intervention),
        "full_behavior_distinct_count": len(full_behavior),
        "preferred_intervention_distinct_count": int(
            gate["preferred_intervention_distinct_pairs"]
        ),
        "preferred_intervention_capacity_met": len(intervention)
        >= int(gate["preferred_intervention_distinct_pairs"]),
        "intervention_semantic_family_count": len(families),
        "intervention_semantic_families": sorted(families),
        "intervention_selected_operation_types": sorted(operations),
        "intervention_selected_proposed_tools": sorted(proposed_tools),
        "selected_memory_counts_on_intervention_pairs": dict(
            sorted(selected_counts.items())
        ),
        "maximum_single_selected_memory_share": maximum_share,
        "target_policy_alignment_count": len(aligned),
        "stop_target_count": len(stop_targets),
        "stop_target_safety_preserved_count": len(stop_safe),
        "target_policy_counts": dict(
            sorted(Counter(record["target_policy_type"] for record in records).items())
        ),
        "rank1_operation_counts": dict(
            sorted(Counter(record["rank1_operation"] for record in records).items())
        ),
        "selected_operation_counts": dict(
            sorted(Counter(record["selected_operation"] for record in records).items())
        ),
        "capacity_checks": checks,
        "future_model_pilot_preparation_authorized": all(checks.values()),
        "gpu_run_authorized": False,
    }


def prepare(config_path: Path = CONFIG) -> dict[str, Any]:
    config = load_config(config_path)
    inventory_path = resolve_and_verify(config["inputs"]["dynamic_inventory"])
    smoke_path = resolve_and_verify(config["inputs"]["scripted_smoke"])
    manifest_path = resolve_and_verify(
        config["inputs"]["legacy_selection_manifest"]
    )
    prior_path = resolve_and_verify(
        config["inputs"]["prior_selector_screening"]
    )
    action_path, action_payload = action_memory_output(config)
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    smoke = json.loads(smoke_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    prior = json.loads(prior_path.read_text(encoding="utf-8"))
    if not inventory["dynamic_inventory_ready"] or not smoke["scripted_smoke_passed"]:
        raise RuntimeError("upstream ToolSandbox validation did not pass")

    source_families = set(str(value) for value in config["source_families"])
    target_families = set(str(value) for value in config["target_profiles"])
    overlap = source_families & target_families
    if overlap:
        raise RuntimeError(f"source/target semantic-family overlap: {sorted(overlap)}")

    action_definitions = {
        str(card["experience_id"]): dict(card)
        for card in action_payload["memory_cards"]
    }
    action_experiences = [
        Experience(
            experience_id=experience_id,
            source_instance_id=str(card["source_family"]),
            natural_text=str(card["natural_text"]),
            policy=base.policy_for_retrieval(
                base.RecoveryOperation(str(card["recovery_operation"]))
            ),
            provenance="toolsandbox_scripted_action_memory",
        )
        for experience_id, card in sorted(action_definitions.items())
    ]
    stop_config = dict(config)
    stop_config["toolsandbox_memory_cards"] = config["stop_memory_cards"]
    stop_experiences, stop_definitions = base.configured_toolsandbox_memories(
        stop_config
    )
    legacy_experiences, legacy_definitions = base.configured_legacy_memories(
        config, manifest
    )
    experiences = action_experiences + stop_experiences + legacy_experiences
    if int(config["retrieval"]["top_k"]) != len(experiences):
        raise RuntimeError("top_k must expose the complete frozen pilot memory bank")
    retriever = SourceBlindTfidfRetriever(experiences)

    repository = ROOT / "external" / "toolsandbox"
    sys.path.insert(0, str(repository))
    try:
        from tool_sandbox.common.execution_context import (  # type: ignore
            DatabaseNamespace,
            RoleType,
        )
        from tool_sandbox.common.tool_discovery import ToolBackend  # type: ignore
        from tool_sandbox.scenarios import named_scenarios  # type: ignore
    except ImportError as error:
        raise RuntimeError(
            "ToolSandbox dependencies are unavailable; run inside the "
            "proper-toolsandbox environment"
        ) from error
    random.seed(0)
    scenarios = named_scenarios(preferred_tool_backend=ToolBackend.DEFAULT)
    inventory_records = {
        str(record["name"]): record for record in inventory["records"]
    }

    records = []
    for name, metadata in sorted(inventory_records.items()):
        family = str(metadata["semantic_family"])
        if family not in target_families:
            continue
        scenario = scenarios[name]
        sandbox = scenario.starting_context.get_database(
            DatabaseNamespace.SANDBOX,
            drop_sandbox_message_index=False,
            get_all_history_snapshots=True,
        )
        user_messages = [
            row
            for row in sandbox.iter_rows(named=True)
            if row["sender"] == RoleType.USER
            and row["recipient"] == RoleType.AGENT
        ]
        if not user_messages:
            raise RuntimeError(f"target has no user instruction: {name}")
        instruction = str(user_messages[-1]["content"])
        profile = config["target_profiles"][family]
        target = base.target_observation(
            instruction=instruction,
            tools=list(metadata["tools"]),
            profile=profile,
        )
        query_text = (
            f"{instruction} Failed tool {target.tool_name}. "
            f"Error {target.error_code}. "
            f"Evidence {' '.join(target.evidence_codes)}."
        )
        ranked = retriever.retrieve(
            FailureQuery(
                instance_id=name,
                natural_text=query_text,
                provenance="toolsandbox_target",
            ),
            top_k=int(config["retrieval"]["top_k"]),
        )
        cards = []
        for item in ranked:
            experience_id = item.experience.experience_id
            kwargs = {"rank": item.rank, "score": round(item.score, 12)}
            if experience_id in action_definitions:
                cards.append(
                    base.toolsandbox_card(action_definitions[experience_id], **kwargs)
                )
            elif experience_id in stop_definitions:
                cards.append(
                    base.toolsandbox_card(stop_definitions[experience_id], **kwargs)
                )
            else:
                cards.append(
                    base.legacy_card(legacy_definitions[experience_id], **kwargs)
                )
        decision = select_memory(
            target,
            cards,
            minimum_extraction_confidence=float(
                config["selector"]["minimum_extraction_confidence"]
            ),
        )
        rank1 = min(cards, key=lambda card: card.original_rank)
        selected = next(
            card
            for card in cards
            if card.experience_id == decision.selected_experience_id
        )
        records.append(
            {
                "scenario_name": name,
                "semantic_family": family,
                "instruction": instruction,
                "target_policy_type": str(profile["policy_type"]),
                "target_tool_name": target.tool_name,
                "rank1_experience_id": rank1.experience_id,
                "rank1_operation": rank1.recovery_operation.value,
                "rank1_proposed_action": canonical_action(rank1),
                "rank1_continuation_policy": rank1.continuation_policy.value,
                "rank1_stop_conditions": list(rank1.stop_conditions),
                "selected_experience_id": selected.experience_id,
                "selected_operation": selected.recovery_operation.value,
                "selected_proposed_action": canonical_action(selected),
                "selected_continuation_policy": selected.continuation_policy.value,
                "selected_stop_conditions": list(selected.stop_conditions),
                "selected_original_rank": selected.original_rank,
                "selection_changed": decision.selection_changed,
                "operation_changed": (
                    rank1.recovery_operation != selected.recovery_operation
                ),
                "intervention_distinct": (
                    intervention_signature(rank1)
                    != intervention_signature(selected)
                ),
                "full_behavior_distinct": (
                    full_behavior_signature(rank1)
                    != full_behavior_signature(selected)
                ),
                "selection_decision": decision.to_mapping(),
            }
        )

    summary = summarize(records, config)
    return {
        "schema_version": 2,
        "run_kind": "proper_v2_toolsandbox_cpu_behavioral_selector_capacity",
        "identities": {
            "config_sha256": sha256_file(config_path),
            "dynamic_inventory_sha256": sha256_file(inventory_path),
            "scripted_smoke_sha256": sha256_file(smoke_path),
            "legacy_selection_manifest_sha256": sha256_file(manifest_path),
            "prior_selector_screening_sha256": sha256_file(prior_path),
            "action_memory_preparation_sha256": sha256_file(action_path),
        },
        "source_target_split": {
            "source_families": sorted(source_families),
            "target_families": sorted(target_families),
            "overlap_count": 0,
            "action_memory_count": len(action_experiences),
            "stop_memory_count": len(stop_experiences),
            "legacy_memory_count": len(legacy_experiences),
        },
        "prior_screening_audit": {
            "reported_identity_changed_count": prior["summary"][
                "selection_changed_count"
            ],
            "recomputed_operation_changed_count": sum(
                record["rank1_operation"] != record["selected_operation"]
                for record in prior["records"]
            ),
        },
        "summary": summary,
        "records": records,
        "boundary": dict(config["boundary"]),
        "interpretation_limits": {
            "identity_change_is_not_intervention_change": True,
            "selector_capacity_is_not_model_effect": True,
            "target_scenarios_were_not_played": True,
            "insufficient_information_policy_is_stop_not_ask_user": True,
            "confirmatory_claim_not_authorized": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit behaviorally distinct ToolSandbox selector capacity."
    )
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    config = load_config(args.config)
    result = prepare(args.config)
    output = args.output or ROOT / config["output"]["path"]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "source_target_split": result["source_target_split"],
                "prior_screening_audit": result["prior_screening_audit"],
                "summary": result["summary"],
                "boundary": result["boundary"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    status = (
        "PASS"
        if result["summary"]["future_model_pilot_preparation_authorized"]
        else "STOP"
    )
    print(f"RESULT={status}_PROPER_V2_TOOLSANDBOX_BEHAVIORAL_CAPACITY")
    print("NOTE=No target scenario was played and no model output was used.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
