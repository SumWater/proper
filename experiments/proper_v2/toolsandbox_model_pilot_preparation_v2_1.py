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
    / "toolsandbox_model_pilot_preparation_v2_1.yaml"
)
sys.path.insert(0, str(ROOT / "experiments" / "proper_v2"))

from qwen_jsonl_worker_v2_1 import response, validate_request  # noqa: E402


def canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("status") != "preparation_before_toolsandbox_model_outputs":
        raise RuntimeError("ToolSandbox model-pilot preparation status is invalid")
    boundary = config["boundary"]
    if (
        boundary["gpu_run_authorized"]
        or boundary["model_loaded"]
        or boundary["model_outputs_read"]
    ):
        raise RuntimeError("preparation config cannot authorize model execution")
    return config


def resolve_and_verify(value: Mapping[str, Any]) -> Path:
    path = ROOT / str(value["path"])
    if not path.is_file():
        raise RuntimeError(f"frozen input is missing: {path}")
    observed = sha256_file(path)
    if observed != str(value["sha256"]):
        raise RuntimeError(
            f"frozen input hash mismatch: {path}; "
            f"expected={value['sha256']} observed={observed}"
        )
    return path


def load_frozen_inputs(
    config: Mapping[str, Any],
) -> tuple[dict[str, Path], dict[str, dict[str, Any]]]:
    paths = {
        name: resolve_and_verify(value)
        for name, value in config["frozen_inputs"].items()
    }
    payloads = {
        name: json.loads(path.read_text(encoding="utf-8"))
        for name, path in paths.items()
    }
    capacity = payloads["phase_aware_capacity"]
    if not capacity["phase_aware_capacity_passed"]:
        raise RuntimeError("phase-aware capacity did not pass")
    if not capacity["behavioral_summary"][
        "future_model_pilot_preparation_authorized"
    ]:
        raise RuntimeError("capacity did not authorize model-pilot preparation")
    if capacity["boundary"]["model_loaded"] or capacity["boundary"][
        "model_outputs_read"
    ]:
        raise RuntimeError("capacity input unexpectedly contains model activity")
    return paths, payloads


def extract_legacy_text(prompt: str) -> str:
    marker = "RETRIEVED_PAST_EXPERIENCE="
    suffix = "\nUse the past experience only if it is applicable"
    if marker not in prompt or suffix not in prompt:
        raise RuntimeError("legacy prompt does not contain retrievable memory")
    return prompt.split(marker, 1)[1].split(suffix, 1)[0]


def legacy_memory_cards(
    manifest: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    cards: dict[str, dict[str, Any]] = {}
    for record in manifest["records"]:
        experience_id = str(record["baseline_rank1_experience_id"])
        if experience_id in cards:
            continue
        candidates = [
            item["candidate"]
            for item in record["proper_top10"]
            if item["candidate"]["experience_id"] == experience_id
        ]
        if len(candidates) != 1:
            raise RuntimeError(f"legacy memory metadata missing: {experience_id}")
        candidate = candidates[0]
        operation = {
            "repair": "repair_arguments",
            "retry": "retry_same_action",
            "stop": "stop_and_report",
        }[str(candidate["policy_from_text"])]
        cards[experience_id] = {
            "experience_id": experience_id,
            "natural_text": extract_legacy_text(str(record["prompt"])),
            "recovery_operation": operation,
            "proposed_action": None,
            "continuation_policy": (
                "terminate"
                if operation == "stop_and_report"
                else "retry_then_verify"
                if operation == "retry_same_action"
                else "verify_then_continue"
            ),
            "stop_conditions": (
                ["persistent_authorization_denial"]
                if operation == "stop_and_report"
                else []
            ),
        }
    return cards


def memory_bank(payloads: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    behavioral = payloads["behavioral_capacity_config"]
    action = payloads["action_memory_preparation"]
    cards = legacy_memory_cards(payloads["legacy_selection_manifest"])
    for raw in action["memory_cards"]:
        card = dict(raw)
        cards[str(card["experience_id"])] = card
    for raw in behavioral["stop_memory_cards"]:
        card = dict(raw)
        card.setdefault("proposed_action", None)
        cards[str(card["experience_id"])] = card
    return cards


def compact_memory(card: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "experience_id": str(card["experience_id"]),
        "natural_text": str(card["natural_text"]),
        "recovery_operation": str(card["recovery_operation"]),
        "proposed_action": card.get("proposed_action"),
        "continuation_policy": str(card["continuation_policy"]),
        "stop_conditions": list(card.get("stop_conditions", ())),
    }


def tool_schemas(
    tool_names: list[str],
    all_tools: Mapping[str, Any],
    converter: Any,
) -> list[dict[str, Any]]:
    missing = sorted(set(tool_names) - set(all_tools))
    if missing:
        raise RuntimeError(f"ToolSandbox tools unavailable: {missing}")
    selected = {name: all_tools[name] for name in sorted(set(tool_names))}
    return list(converter(selected))


def agent_messages(
    *,
    observation: Mapping[str, Any],
    tools: list[Mapping[str, Any]],
    memory: Mapping[str, Any],
    budget: Mapping[str, Any],
) -> list[dict[str, str]]:
    system = (
        "You are a stateful tool-using agent continuing a user task. "
        "Return exactly one JSON object and no other text. "
        'To call a tool use {"kind":"tool","tool_name":string,'
        '"arguments":object}. To stop safely use '
        '{"kind":"stop","reason_code":string,"message":string}. '
        "Use only an available tool and follow its argument schema. "
        "At pre_action, do not invent missing information. At post_failure, "
        "recover when a compatible safe prerequisite exists, then continue "
        "the original task. Use the retrieved memory only if applicable."
    )
    user = "\n".join(
        [
            f"OBSERVABLE_RECOVERY_STATE={canonical(observation)}",
            f"AVAILABLE_TOOLS={canonical(tools)}",
            f"RETRIEVED_MEMORY={canonical(memory)}",
            f"REMAINING_BUDGET={canonical(budget)}",
            "Choose the single next decision.",
        ]
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def prepare_payload(config_path: Path = CONFIG) -> dict[str, Any]:
    config = load_config(config_path)
    paths, payloads = load_frozen_inputs(config)
    capacity = payloads["phase_aware_capacity"]
    behavioral = payloads["behavioral_capacity_config"]
    inventory = {
        str(item["name"]): item
        for item in payloads["dynamic_inventory"]["records"]
    }
    cards = memory_bank(payloads)
    profiles = behavioral["target_profiles"]

    repository = ROOT / "external" / "toolsandbox"
    sys.path.insert(0, str(repository))
    try:
        from tool_sandbox.common.tool_conversion import (  # type: ignore
            convert_to_openai_tools,
        )
        from tool_sandbox.common.tool_discovery import (  # type: ignore
            ToolBackend,
            get_all_tools,
        )
    except ImportError as exc:
        raise RuntimeError(
            "ToolSandbox dependencies are unavailable; run preparation "
            "inside the proper-toolsandbox environment"
        ) from exc
    random.seed(0)
    available_tool_map = get_all_tools(ToolBackend.DEFAULT)

    primary = [
        item for item in capacity["records"] if item["intervention_distinct"]
    ]
    cohort = config["cohort"]
    if len(primary) != int(cohort["expected_pair_count"]):
        raise RuntimeError("primary intervention-distinct count changed")

    conditions = list(cohort["conditions_in_fixed_order"])
    records = []
    phase_counts: Counter[str] = Counter()
    memory_counts: Counter[str] = Counter()
    prompt_hashes: set[str] = set()
    for pair_index, record in enumerate(primary, start=1):
        name = str(record["scenario_name"])
        family = str(record["semantic_family"])
        phase = str(record["decision_phase"])
        metadata = inventory[name]
        profile = profiles[family]
        names = sorted(str(value) for value in metadata["tools"])
        schemas = tool_schemas(
            names, available_tool_map, convert_to_openai_tools
        )
        prefix_recipe = None
        if phase == "post_failure":
            prefix_recipe = config["post_failure_prefix_recipes"].get(family)
            if prefix_recipe is None:
                raise RuntimeError(
                    f"post-failure prefix recipe missing: {family}"
                )
            action = dict(prefix_recipe["failed_action"])
            if action["tool_name"] != str(profile["failed_tool"]):
                raise RuntimeError(
                    f"failed tool and prefix recipe disagree: {family}"
                )
            prefix_tool_names = [
                str(item["tool_name"])
                for item in prefix_recipe["prelude_actions"]
            ] + [str(action["tool_name"])]
            if not set(prefix_tool_names).issubset(names):
                raise RuntimeError(
                    f"prefix recipe uses unavailable tool: {family}"
                )
        else:
            action = {
                "tool_name": str(profile["failed_tool"]),
                "arguments": dict(profile.get("failed_arguments", {})),
            }
        observation = {
            "phase": phase,
            "instruction": str(record["instruction"]),
            "action": action,
            "error_code": (
                str(profile["error_code"]) if phase == "post_failure" else None
            ),
            "evidence_codes": list(profile["evidence_codes"]),
            "satisfied_facts": list(profile.get("satisfied_facts", ())),
            "available_tool_names": names,
        }
        ids = {
            "tfidf_rank1_memory": str(record["rank1_experience_id"]),
            "proper_v2_1_memory": str(record["selected_experience_id"]),
        }
        condition_payloads = {}
        for condition in conditions:
            experience_id = ids[condition]
            if experience_id not in cards:
                raise RuntimeError(f"memory card missing: {experience_id}")
            memory = compact_memory(cards[experience_id])
            messages = agent_messages(
                observation=observation,
                tools=schemas,
                memory=memory,
                budget={
                    "decisions_left": int(
                        config["agent_budget"][
                            "maximum_decisions_after_branch"
                        ]
                    ),
                    "tool_calls_left": int(
                        config["agent_budget"][
                            "maximum_tool_calls_after_branch"
                        ]
                    ),
                },
            )
            request = validate_request(
                {
                    "request_id": f"pair-{pair_index:02d}:{condition}:step-01",
                    "messages": messages,
                    "seed": int(config["model"]["seed"]),
                    "max_new_tokens": int(config["model"]["max_new_tokens"]),
                }
            )
            request_hash = sha256_text(canonical(request))
            prompt_hashes.add(request_hash)
            memory_counts[experience_id] += 1
            condition_payloads[condition] = {
                "experience_id": experience_id,
                "memory": memory,
                "initial_request": request,
                "initial_request_sha256": request_hash,
            }
        phase_counts[phase] += 1
        records.append(
            {
                "pair_id": f"toolsandbox-v2-1-{pair_index:02d}",
                "scenario_name": name,
                "semantic_family": family,
                "decision_phase": phase,
                "instruction": str(record["instruction"]),
                "branch_action": action,
                "branch_prefix_recipe": (
                    dict(prefix_recipe) if prefix_recipe is not None else None
                ),
                "target_policy_type": str(record["target_policy_type"]),
                "available_tool_names": names,
                "available_tool_schemas_sha256": sha256_text(canonical(schemas)),
                "selection_decision_sha256": sha256_text(
                    canonical(record["selection_decision"])
                ),
                "conditions": condition_payloads,
            }
        )

    checks = {
        "pair_count_frozen": len(records)
        == int(cohort["expected_pair_count"]),
        "post_failure_count_frozen": phase_counts["post_failure"]
        == int(cohort["expected_post_failure_pair_count"]),
        "pre_action_count_frozen": phase_counts["pre_action"]
        == int(cohort["expected_pre_action_pair_count"]),
        "condition_count_frozen": all(
            len(item["conditions"])
            == int(cohort["expected_condition_count_per_pair"])
            for item in records
        ),
        "all_initial_requests_distinct": len(prompt_hashes)
        == len(records) * len(conditions),
        "condition_order_frozen": conditions
        == ["tfidf_rank1_memory", "proper_v2_1_memory"],
        "no_source_target_family_overlap": not (
            set(capacity["source_target_split"]["source_families"])
            & {item["semantic_family"] for item in records}
        ),
    }
    payload = {
        "schema_version": 1,
        "run_kind": "proper_v2_1_toolsandbox_model_pilot_prepared",
        "identities": {
            "config_sha256": sha256_file(config_path),
            "frozen_input_sha256": {
                name: sha256_file(path) for name, path in paths.items()
            },
        },
        "cohort": {
            "primary_pair_count": len(records),
            "phase_counts": dict(sorted(phase_counts.items())),
            "condition_order": conditions,
            "planned_initial_model_call_count": len(records) * len(conditions),
            "distinct_initial_request_count": len(prompt_hashes),
            "secondary_preservation_pair_count": int(
                cohort["secondary_preservation_pair_count"]
            ),
            "memory_exposure_counts": dict(sorted(memory_counts.items())),
        },
        "preparation_checks": checks,
        "ready_for_runner_implementation": all(checks.values()),
        "model_protocol": dict(config["model"]),
        "agent_budget": dict(config["agent_budget"]),
        "evaluation": dict(config["evaluation"]),
        "records": records,
        "boundary": dict(config["boundary"]),
        "interpretation_limits": {
            "capacity_selected_exploratory_pilot": True,
            "phases_must_be_reported_separately": True,
            "not_evidence_for_all_agent_memory_scenarios": True,
            "gpu_run_not_yet_authorized": True,
        },
    }
    payload["identities"]["prepared_payload_sha256"] = sha256_text(
        canonical(payload)
    )
    return payload


def write_payload(payload: Mapping[str, Any], config: Mapping[str, Any]) -> None:
    prepared = ROOT / str(config["outputs"]["prepared_manifest"])
    screening = ROOT / str(config["outputs"]["screening"])
    prepared.parent.mkdir(parents=True, exist_ok=True)
    screening.parent.mkdir(parents=True, exist_ok=True)
    prepared.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    compact = {key: value for key, value in payload.items() if key != "records"}
    compact["run_kind"] = (
        "proper_v2_1_toolsandbox_model_pilot_preparation_screening"
    )
    screening.write_text(
        json.dumps(compact, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def cpu_dry_run(config_path: Path = CONFIG) -> dict[str, Any]:
    config = load_config(config_path)
    _, payloads = load_frozen_inputs(config)
    records = payloads["phase_aware_capacity"]["records"]
    primary = [item for item in records if item["intervention_distinct"]]
    phase_counts = Counter(item["decision_phase"] for item in primary)
    synthetic_request = validate_request(
        {
            "request_id": "synthetic:tfidf_rank1_memory:step-01",
            "messages": [
                {"role": "system", "content": "Return exactly one JSON object."},
                {"role": "user", "content": "Synthetic protocol check."},
            ],
            "seed": int(config["model"]["seed"]),
            "max_new_tokens": int(config["model"]["max_new_tokens"]),
        }
    )
    synthetic_response = response(
        synthetic_request,
        raw_text='{"kind":"stop","reason_code":"synthetic_cpu_dry_run"}',
        synthetic=True,
    )
    checks = {
        "primary_pair_count_frozen": len(primary)
        == int(config["cohort"]["expected_pair_count"]),
        "post_failure_count_frozen": phase_counts["post_failure"]
        == int(config["cohort"]["expected_post_failure_pair_count"]),
        "pre_action_count_frozen": phase_counts["pre_action"]
        == int(config["cohort"]["expected_pre_action_pair_count"]),
        "worker_request_round_trip_valid": (
            synthetic_response["request_id"] == synthetic_request["request_id"]
            and synthetic_response["synthetic_non_model_output"]
        ),
    }
    return {
        "checks": checks,
        "primary_pair_count": len(primary),
        "phase_counts": dict(sorted(phase_counts.items())),
        "planned_initial_model_call_count": len(primary) * 2,
        "model_loaded": False,
        "model_outputs_read": False,
        "target_scenario_played": False,
        "synthetic_non_model_output": True,
        "gpu_run_authorized": False,
        "passed": all(checks.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Freeze the PROPER v2.1 ToolSandbox model-pilot manifest."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--cpu-dry-run", action="store_true")
    mode.add_argument("--prepare", action="store_true")
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()
    if args.cpu_dry_run:
        result = cpu_dry_run(args.config)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        status = "PASS" if result["passed"] else "STOP"
        print(f"RESULT={status}_PROPER_V2_1_TOOLSANDBOX_MODEL_PILOT_DRY_RUN")
        print("NOTE=No scenario was played and no model was loaded.")
        return 0

    config = load_config(args.config)
    payload = prepare_payload(args.config)
    write_payload(payload, config)
    print(
        json.dumps(
            {
                "cohort": payload["cohort"],
                "preparation_checks": payload["preparation_checks"],
                "ready_for_runner_implementation": payload[
                    "ready_for_runner_implementation"
                ],
                "boundary": payload["boundary"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    status = "PASS" if payload["ready_for_runner_implementation"] else "STOP"
    print(f"RESULT={status}_PROPER_V2_1_TOOLSANDBOX_MODEL_PILOT_PREPARATION")
    print("NOTE=No target scenario was played and no model was loaded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
