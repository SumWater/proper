from __future__ import annotations

import argparse
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
    / "toolsandbox_selector_capacity_v2_1.yaml"
)
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments" / "proper_v2"))

import toolsandbox_selector_capacity_v2 as behavioral_v2  # noqa: E402
from failure_memory.proper_v2 import (  # noqa: E402
    DecisionPhase,
    ObservableRecoveryState,
    ProposedAction,
    RetrySafety,
    RetrySafetyAssessment,
)


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if (
        config.get("status")
        != "proper_v2_1_phase_aware_cpu_capacity_before_model_outputs"
    ):
        raise RuntimeError("PROPER v2.1 phase-aware config has invalid status")
    return config


def resolve_and_verify(value: Mapping[str, Any]) -> Path:
    path = ROOT / str(value["path"])
    if behavioral_v2.sha256_file(path) != str(value["sha256"]):
        raise RuntimeError(f"frozen source mismatch: {path}")
    return path


def phase_aware_target(
    *,
    instruction: str,
    tools: list[str],
    profile: Mapping[str, Any],
) -> ObservableRecoveryState:
    failed_tool = str(profile["failed_tool"])
    if failed_tool not in tools:
        raise RuntimeError(f"observed action tool unavailable: {failed_tool}")
    policy_type = str(profile["policy_type"])
    phase = (
        DecisionPhase.PRE_ACTION
        if policy_type == "stop_and_report"
        else DecisionPhase.POST_FAILURE
    )
    return ObservableRecoveryState(
        phase=phase,
        instruction=instruction,
        action=ProposedAction(
            tool_name=failed_tool,
            argument_template=dict(profile.get("failed_arguments", {})),
        ),
        error_code=(
            None
            if phase == DecisionPhase.PRE_ACTION
            else str(profile["error_code"])
        ),
        evidence_codes=tuple(profile["evidence_codes"]),
        failed_argument_paths=(),
        missing_fields=(),
        public_schema_fields=(),
        public_required_fields=(),
        available_tools=tuple(tools),
        available_capabilities=(
            "invoke_prerequisite",
            "request_information",
            "stop_and_report",
        ),
        satisfied_facts=tuple(profile.get("satisfied_facts", ())),
        violated_facts=(),
        repeated_same_call_count=(
            0 if phase == DecisionPhase.PRE_ACTION else 1
        ),
        retry_safety=(
            RetrySafetyAssessment(RetrySafety.UNKNOWN)
            if phase == DecisionPhase.PRE_ACTION
            else RetrySafetyAssessment(
                RetrySafety.UNSAFE,
                (behavioral_v2.base.UNSAFE_RETRY_EVIDENCE,),
            )
        ),
    )


def prepare(config_path: Path = CONFIG) -> dict[str, Any]:
    config = load_config(config_path)
    base_config_path = resolve_and_verify(
        config["base_behavioral_capacity_config"]
    )
    for value in config["method_sources"].values():
        resolve_and_verify(value)

    # The v2 behavioral audit exposes one target-construction seam through its
    # imported base module. Replace it only for this synchronous reconstruction,
    # then restore it even if validation fails.
    original_factory = behavioral_v2.base.target_observation
    behavioral_v2.base.target_observation = phase_aware_target
    try:
        result = behavioral_v2.prepare(base_config_path)
    finally:
        behavioral_v2.base.target_observation = original_factory

    phase_mapping = config["phase_mapping"]
    phase_counts: Counter[str] = Counter()
    intervention_phase_counts: Counter[str] = Counter()
    method_versions: Counter[str] = Counter()
    for record in result["records"]:
        phase = str(phase_mapping[record["target_policy_type"]])
        record["decision_phase"] = phase
        phase_counts[phase] += 1
        if record["intervention_distinct"]:
            intervention_phase_counts[phase] += 1
        method = str(record["selection_decision"]["method_version"])
        method_versions[method] += 1

    expected = config["expected"]
    checks = {
        "valid_target_count_met": len(result["records"])
        == int(expected["valid_target_count"]),
        "post_failure_count_met": phase_counts["post_failure"]
        == int(expected["post_failure_count"]),
        "pre_action_count_met": phase_counts["pre_action"]
        == int(expected["pre_action_count"]),
        "intervention_distinct_capacity_met": result["summary"][
            "intervention_distinct_count"
        ]
        >= int(expected["minimum_intervention_distinct_count"]),
        "post_failure_intervention_capacity_met": intervention_phase_counts[
            "post_failure"
        ]
        >= int(expected["minimum_post_failure_intervention_count"]),
        "pre_action_intervention_capacity_met": intervention_phase_counts[
            "pre_action"
        ]
        >= int(expected["minimum_pre_action_intervention_count"]),
        "method_version_frozen": set(method_versions)
        == {str(expected["required_method_version"])},
        "base_behavioral_capacity_checks_preserved": all(
            result["summary"]["capacity_checks"].values()
        ),
    }
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_1_toolsandbox_phase_aware_cpu_capacity",
        "identities": {
            "config_sha256": behavioral_v2.sha256_file(config_path),
            "base_behavioral_capacity_config_sha256": behavioral_v2.sha256_file(
                base_config_path
            ),
            "method_source_sha256": {
                key: behavioral_v2.sha256_file(
                    ROOT / str(value["path"])
                )
                for key, value in config["method_sources"].items()
            },
            "reconstructed_behavioral_screening_sha256": (
                behavioral_v2.sha256_file(
                    ROOT
                    / "outputs"
                    / "proper_v2"
                    / "toolsandbox_selector_capacity_v2"
                    / "screening.json"
                )
            ),
        },
        "phase_counts": dict(sorted(phase_counts.items())),
        "intervention_phase_counts": dict(
            sorted(intervention_phase_counts.items())
        ),
        "method_version_counts": dict(sorted(method_versions.items())),
        "phase_aware_checks": checks,
        "phase_aware_capacity_passed": all(checks.values()),
        "behavioral_summary": result["summary"],
        "source_target_split": result["source_target_split"],
        "records": result["records"],
        "boundary": dict(config["boundary"]),
        "interpretation_limits": {
            "pre_action_and_post_failure_require_stratified_evaluation": True,
            "capacity_is_not_model_effect": True,
            "no_model_output_used": True,
            "confirmatory_claim_not_authorized": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the PROPER v2.1 phase-aware ToolSandbox CPU audit."
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
                "phase_counts": result["phase_counts"],
                "intervention_phase_counts": result[
                    "intervention_phase_counts"
                ],
                "method_version_counts": result["method_version_counts"],
                "phase_aware_checks": result["phase_aware_checks"],
                "behavioral_summary": result["behavioral_summary"],
                "boundary": result["boundary"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    status = "PASS" if result["phase_aware_capacity_passed"] else "STOP"
    print(f"RESULT={status}_PROPER_V2_1_PHASE_AWARE_CAPACITY")
    print("NOTE=No target scenario was played and no model output was used.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
