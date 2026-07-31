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
    ROOT / "configs" / "proper_v2" / "toolsandbox_selector_capacity.yaml"
)
sys.path.insert(0, str(ROOT / "src"))

from failure_memory.contracts import (  # noqa: E402
    PolicyKind,
    RecoveryPolicy,
)
from failure_memory.proper_v2 import (  # noqa: E402
    ContinuationPolicy,
    MemoryPolicyCard,
    ObservableFailure,
    ProposedAction,
    RecoveryOperation,
    RetrySafety,
    RetrySafetyAssessment,
    select_memory,
)
from failure_memory.retrieval import (  # noqa: E402
    Experience,
    FailureQuery,
    SourceBlindTfidfRetriever,
)


UNSAFE_RETRY_EVIDENCE = "public_contract:missing_prerequisite_or_information"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if (
        config.get("status")
        != "exploratory_cpu_selector_capacity_before_toolsandbox_model_outputs"
    ):
        raise RuntimeError("ToolSandbox selector-capacity config has invalid status")
    return config


def resolve_and_verify_input(value: Mapping[str, Any]) -> Path:
    path = ROOT / str(value["path"])
    if sha256_file(path) != str(value["sha256"]):
        raise RuntimeError(f"input hash mismatch: {path}")
    return path


def policy_for_retrieval(operation: RecoveryOperation) -> RecoveryPolicy:
    if operation == RecoveryOperation.RETRY_SAME_ACTION:
        return RecoveryPolicy(PolicyKind.RETRY, {"max_attempts": 1})
    if operation == RecoveryOperation.REPAIR_ARGUMENTS:
        return RecoveryPolicy(
            PolicyKind.REVISE_ARGUMENTS,
            {"operation": "replace", "fields": [], "bindings": {}},
        )
    return RecoveryPolicy(
        PolicyKind.STOP_AND_REPORT,
        {"reason_code": operation.value},
    )


def configured_toolsandbox_memories(
    config: Mapping[str, Any],
) -> tuple[list[Experience], dict[str, dict[str, Any]]]:
    experiences: list[Experience] = []
    definitions: dict[str, dict[str, Any]] = {}
    for raw in config["toolsandbox_memory_cards"]:
        value = dict(raw)
        experience_id = str(value["experience_id"])
        operation = RecoveryOperation(str(value["recovery_operation"]))
        definitions[experience_id] = value
        experiences.append(
            Experience(
                experience_id=experience_id,
                source_instance_id=str(value["source_family"]),
                natural_text=str(value["natural_text"]),
                policy=policy_for_retrieval(operation),
                provenance="toolsandbox_source_family",
            )
        )
    return experiences, definitions


def extract_retrieved_text(prompt: str) -> str:
    marker = "RETRIEVED_PAST_EXPERIENCE="
    suffix = "\nUse the past experience only if it is applicable"
    if marker not in prompt or suffix not in prompt:
        raise RuntimeError("legacy prompt does not contain a retrievable memory")
    return prompt.split(marker, 1)[1].split(suffix, 1)[0]


def configured_legacy_memories(
    config: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> tuple[list[Experience], dict[str, dict[str, Any]]]:
    wanted = set(str(value) for value in config["legacy_memory_ids"])
    experiences: list[Experience] = []
    definitions: dict[str, dict[str, Any]] = {}
    for record in manifest["records"]:
        experience_id = str(record["baseline_rank1_experience_id"])
        if experience_id not in wanted or experience_id in definitions:
            continue
        matches = [
            item
            for item in record["proper_top10"]
            if item["candidate"]["experience_id"] == experience_id
        ]
        if len(matches) != 1:
            raise RuntimeError(f"legacy candidate metadata missing: {experience_id}")
        candidate = matches[0]["candidate"]
        policy_name = str(candidate["policy_from_text"])
        operation = {
            "repair": RecoveryOperation.REPAIR_ARGUMENTS,
            "retry": RecoveryOperation.RETRY_SAME_ACTION,
            "stop": RecoveryOperation.STOP_AND_REPORT,
        }[policy_name]
        natural_text = extract_retrieved_text(str(record["prompt"]))
        source_failure = dict(candidate["source_failure"])
        definitions[experience_id] = {
            "experience_id": experience_id,
            "natural_text": natural_text,
            "operation": operation.value,
            "source_failure": source_failure,
            "repair_targets": list(candidate.get("repair_targets", [])),
        }
        experiences.append(
            Experience(
                experience_id=experience_id,
                source_instance_id=experience_id,
                natural_text=natural_text,
                policy=policy_for_retrieval(operation),
                provenance="toolmisusebench_frozen_legacy_memory",
            )
        )
    missing = wanted - set(definitions)
    if missing:
        raise RuntimeError(f"legacy memories not found: {sorted(missing)}")
    return experiences, definitions


def toolsandbox_card(
    definition: Mapping[str, Any],
    *,
    rank: int,
    score: float,
) -> MemoryPolicyCard:
    proposed = definition.get("proposed_action")
    return MemoryPolicyCard(
        experience_id=str(definition["experience_id"]),
        natural_text=str(definition["natural_text"]),
        original_rank=rank,
        retrieval_score=score,
        trigger_evidence=tuple(definition.get("trigger_evidence", ())),
        required_preconditions=tuple(definition.get("required_preconditions", ())),
        recovery_operation=RecoveryOperation(str(definition["recovery_operation"])),
        target_object=(
            str(definition["source_tool"])
            if definition.get("source_tool") is not None
            else None
        ),
        proposed_action=(
            ProposedAction(
                tool_name=str(proposed["tool_name"]),
                argument_template=dict(proposed["argument_template"]),
            )
            if isinstance(proposed, Mapping)
            else None
        ),
        repair_targets=(),
        continuation_policy=ContinuationPolicy(
            str(definition["continuation_policy"])
        ),
        success_evidence=("tool_succeeds",),
        stop_conditions=tuple(definition.get("stop_conditions", ())),
        source_tool=(
            str(definition["source_tool"])
            if definition.get("source_tool") is not None
            else None
        ),
        extraction_confidence=1.0,
    )


def legacy_card(
    definition: Mapping[str, Any],
    *,
    rank: int,
    score: float,
) -> MemoryPolicyCard:
    source_failure = definition["source_failure"]
    operation = RecoveryOperation(str(definition["operation"]))
    evidence = []
    if source_failure.get("error_code"):
        evidence.append(f"error_code:{source_failure['error_code']}")
    if source_failure.get("state"):
        evidence.append(f"failure_state:{source_failure['state']}")
    continuation = {
        RecoveryOperation.REPAIR_ARGUMENTS: ContinuationPolicy.VERIFY_THEN_CONTINUE,
        RecoveryOperation.RETRY_SAME_ACTION: ContinuationPolicy.RETRY_THEN_VERIFY,
        RecoveryOperation.STOP_AND_REPORT: ContinuationPolicy.TERMINATE,
    }[operation]
    return MemoryPolicyCard(
        experience_id=str(definition["experience_id"]),
        natural_text=str(definition["natural_text"]),
        original_rank=rank,
        retrieval_score=score,
        trigger_evidence=tuple(evidence),
        required_preconditions=(),
        recovery_operation=operation,
        target_object=str(source_failure["tool_name"]),
        proposed_action=None,
        repair_targets=tuple(definition.get("repair_targets", ())),
        continuation_policy=continuation,
        success_evidence=("tool_succeeds",),
        stop_conditions=(
            ("persistent_authorization_denial",)
            if operation == RecoveryOperation.STOP_AND_REPORT
            else ()
        ),
        source_tool=str(source_failure["tool_name"]),
        extraction_confidence=1.0,
    )


def target_observation(
    *,
    instruction: str,
    tools: list[str],
    profile: Mapping[str, Any],
) -> ObservableFailure:
    failed_tool = str(profile["failed_tool"])
    if failed_tool not in tools:
        raise RuntimeError(f"failed tool is unavailable in target: {failed_tool}")
    return ObservableFailure(
        instruction=instruction,
        tool_name=failed_tool,
        failed_arguments=dict(profile.get("failed_arguments", {})),
        error_code=str(profile["error_code"]),
        evidence_codes=tuple(profile["evidence_codes"]),
        failed_argument_paths=(),
        missing_fields=(),
        public_schema_fields=(),
        public_required_fields=(),
        available_tools=tuple(tools),
        available_capabilities=(
            "invoke_prerequisite",
            "stop_and_report",
        ),
        satisfied_facts=tuple(profile.get("satisfied_facts", ())),
        violated_facts=(),
        repeated_same_call_count=1,
        retry_safety=RetrySafetyAssessment(
            status=RetrySafety.UNSAFE,
            evidence_codes=(UNSAFE_RETRY_EVIDENCE,),
        ),
    )


def summarize(
    records: list[dict[str, Any]], config: Mapping[str, Any]
) -> dict[str, Any]:
    changed = [record for record in records if record["selection_changed"]]
    selected_counts = Counter(
        record["selected_experience_id"] for record in changed
    )
    selected_operations = {
        record["selected_operation"] for record in changed
    }
    changed_families = {
        record["semantic_family"] for record in changed
    }
    maximum = max(selected_counts.values(), default=0)
    maximum_share = maximum / len(changed) if changed else 0.0
    gate = config["capacity_gate"]
    checks = {
        "valid_target_capacity_met": len(records)
        >= int(gate["minimum_valid_targets"]),
        "selection_changed_capacity_met": len(changed)
        >= int(gate["minimum_selection_changed_pairs"]),
        "changed_semantic_family_diversity_met": len(changed_families)
        >= int(gate["minimum_changed_semantic_families"]),
        "changed_operation_diversity_met": len(selected_operations)
        >= int(gate["minimum_changed_selected_operation_types"]),
        "selected_memory_diversity_met": len(selected_counts)
        >= int(gate["minimum_selected_memory_count_on_changed_pairs"]),
        "memory_concentration_limit_met": maximum_share
        <= float(gate["maximum_single_selected_memory_share"]),
    }
    return {
        "valid_target_count": len(records),
        "selection_changed_count": len(changed),
        "preferred_selection_changed_count": int(
            gate["preferred_selection_changed_pairs"]
        ),
        "preferred_selection_changed_capacity_met": len(changed)
        >= int(gate["preferred_selection_changed_pairs"]),
        "target_policy_counts": dict(
            sorted(Counter(record["target_policy_type"] for record in records).items())
        ),
        "rank1_operation_counts": dict(
            sorted(Counter(record["rank1_operation"] for record in records).items())
        ),
        "selected_operation_counts": dict(
            sorted(Counter(record["selected_operation"] for record in records).items())
        ),
        "changed_semantic_family_count": len(changed_families),
        "changed_semantic_families": sorted(changed_families),
        "changed_selected_operation_types": sorted(selected_operations),
        "selected_memory_counts_on_changed_pairs": dict(
            sorted(selected_counts.items())
        ),
        "maximum_single_selected_memory_share": maximum_share,
        "capacity_checks": checks,
        "future_model_pilot_preparation_authorized": all(checks.values()),
        "gpu_run_authorized": False,
    }


def prepare(config_path: Path = CONFIG) -> dict[str, Any]:
    config = load_config(config_path)
    inventory_path = resolve_and_verify_input(config["inputs"]["dynamic_inventory"])
    smoke_path = resolve_and_verify_input(config["inputs"]["scripted_smoke"])
    manifest_path = resolve_and_verify_input(
        config["inputs"]["legacy_selection_manifest"]
    )
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    smoke = json.loads(smoke_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not inventory["dynamic_inventory_ready"] or not smoke["scripted_smoke_passed"]:
        raise RuntimeError("upstream ToolSandbox feasibility gate did not pass")

    source_families = set(str(value) for value in config["source_families"])
    target_families = set(str(value) for value in config["target_profiles"])
    overlap = source_families & target_families
    if overlap:
        raise RuntimeError(f"source/target semantic-family overlap: {sorted(overlap)}")

    ts_experiences, ts_definitions = configured_toolsandbox_memories(config)
    legacy_experiences, legacy_definitions = configured_legacy_memories(
        config, manifest
    )
    experiences = ts_experiences + legacy_experiences
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

    records: list[dict[str, Any]] = []
    inventory_records = {
        str(record["name"]): record for record in inventory["records"]
    }
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
        target = target_observation(
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
            if experience_id in ts_definitions:
                cards.append(toolsandbox_card(ts_definitions[experience_id], **kwargs))
            else:
                cards.append(legacy_card(legacy_definitions[experience_id], **kwargs))
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
                "rank1_score": rank1.retrieval_score,
                "selected_experience_id": selected.experience_id,
                "selected_operation": selected.recovery_operation.value,
                "selected_original_rank": selected.original_rank,
                "selection_changed": decision.selection_changed,
                "abstained": decision.abstained,
                "selection_decision": decision.to_mapping(),
            }
        )

    summary = summarize(records, config)
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_toolsandbox_cpu_selector_capacity",
        "identities": {
            "config_sha256": sha256_file(config_path),
            "dynamic_inventory_sha256": sha256_file(inventory_path),
            "scripted_smoke_sha256": sha256_file(smoke_path),
            "legacy_selection_manifest_sha256": sha256_file(manifest_path),
        },
        "source_target_split": {
            "source_families": sorted(source_families),
            "target_families": sorted(target_families),
            "overlap_count": 0,
            "toolsandbox_memory_count": len(ts_experiences),
            "legacy_memory_count": len(legacy_experiences),
        },
        "summary": summary,
        "records": records,
        "boundary": dict(config["boundary"]),
        "interpretation_limits": {
            "selector_capacity_is_not_model_effect": True,
            "scenario_metadata_and_user_prompt_only": True,
            "no_scenario_was_played": True,
            "insufficient_information_policy_is_stop_not_ask_user": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit ToolSandbox selector-change capacity on CPU."
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
    print(f"RESULT={status}_PROPER_V2_TOOLSANDBOX_SELECTOR_CAPACITY")
    print("NOTE=No scenario was played and no model output was read or generated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
