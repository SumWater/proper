from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from failure_memory.confirmatory import (  # noqa: E402
    aggregate_pair_indicators,
    pair_indicators,
)
from failure_memory.utilization import AgentDecision, DecisionKind  # noqa: E402


RAW = ROOT / "outputs" / "confirmatory_gate_v1" / "results.json"
RAW_SHA256 = "6e44ef0eba2bf7efeed7163d61a621d2a1a5385b6aa507f7ce0417222d2fceb8"
OUTPUT = ROOT / "outputs" / "confirmatory_gate_v1" / "analysis.json"
TOOL_TABLE = ROOT / "outputs" / "confirmatory_gate_v1" / "tool_results.csv"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decision(payload: dict[str, Any]) -> AgentDecision:
    if payload["kind"] == "tool":
        return AgentDecision(
            DecisionKind.TOOL,
            tool_name=str(payload["tool_name"]),
            args=dict(payload["args"]),
        )
    return AgentDecision(DecisionKind.STOP, reason_code=str(payload["reason_code"]))


def condition_metrics(rows: list[dict[str, Any]], condition: str) -> dict[str, Any]:
    outcomes = [row["conditions"][condition]["outcome"] for row in rows]
    return {
        "count": len(rows),
        "recovery_validity_count": sum(item["recovery_validity"] for item in outcomes),
        "recovery_validity_rate": sum(item["recovery_validity"] for item in outcomes)
        / len(rows),
        "task_completion_count": sum(item["task_completion"] for item in outcomes),
        "safety_violation_count": sum(item["safety_violation"] for item in outcomes),
        "repeated_invalid_calls_total": sum(
            item["repeated_invalid_calls"] for item in outcomes
        ),
        "recovery_tool_calls_total": sum(item["recovery_tool_calls"] for item in outcomes),
        "model_output_reuse_count": sum(
            row["conditions"][condition].get("reused_from_condition") is not None
            for row in rows
        ),
    }


def paired_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    indicators = []
    baseline = []
    gate = []
    for row in rows:
        baseline_result = row["conditions"]["tfidf_rank1_memory"]
        gate_result = row["conditions"]["proper_gate_memory"]
        baseline_valid = bool(baseline_result["outcome"]["recovery_validity"])
        gate_valid = bool(gate_result["outcome"]["recovery_validity"])
        baseline.append(baseline_valid)
        gate.append(gate_valid)
        indicators.append(
            pair_indicators(
                no_memory_recovery_validity=baseline_valid,
                memory_recovery_validity=gate_valid,
                no_memory_decision=decision(baseline_result["decision"]),
                memory_decision=decision(gate_result["decision"]),
                strict_policy_adoption=False,
            )
        )
    result = aggregate_pair_indicators(indicators, baseline, gate, alpha=0.05)
    result["directional_hypothesis_supported"] = (
        result["paired_positive_transfer_count"]
        > result["paired_negative_transfer_count"]
        and result["exact_mcnemar_two_sided_p"] < 0.05
    )
    result["hypothesis_direction"] = "ppt_greater_than_pnt"
    return result


def run_analysis() -> dict[str, Any]:
    if sha256_file(RAW) != RAW_SHA256:
        raise RuntimeError("raw Confirmatory Gate v1 result hash mismatch")
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    rows = raw["records"]
    primary = [row for row in rows if row["gate_selection_changed"]]
    if len(rows) != 189 or len(primary) != 115:
        raise RuntimeError("confirmatory population identity mismatch")

    recomputed_primary = paired_metrics(primary)
    for key in (
        "pair_count",
        "paired_negative_transfer_count",
        "paired_positive_transfer_count",
        "paired_risk_difference",
        "exact_mcnemar_two_sided_p",
        "directional_hypothesis_supported",
    ):
        if recomputed_primary[key] != raw["primary_comparison"][key]:
            raise RuntimeError(f"recomputed primary metric differs: {key}")

    by_tool: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in primary:
        by_tool[str(row["failed_action"]["tool_name"])].append(row)
    tool_rows = []
    for tool, members in sorted(by_tool.items()):
        paired = paired_metrics(members)
        tool_rows.append(
            {
                "tool_name": tool,
                "pair_count": len(members),
                "rank1_recovery_validity_count": condition_metrics(
                    members, "tfidf_rank1_memory"
                )["recovery_validity_count"],
                "gate_recovery_validity_count": condition_metrics(
                    members, "proper_gate_memory"
                )["recovery_validity_count"],
                "paired_positive_transfer_count": paired[
                    "paired_positive_transfer_count"
                ],
                "paired_negative_transfer_count": paired[
                    "paired_negative_transfer_count"
                ],
                "memory_induced_action_change_count": paired[
                    "memory_induced_action_change_count"
                ],
                "risk_difference": paired["paired_risk_difference"],
                "exact_mcnemar_two_sided_p": paired[
                    "exact_mcnemar_two_sided_p"
                ],
            }
        )

    improvements = [
        row
        for row in primary
        if row["gate_vs_rank1_indicators"]["paired_positive_transfer"]
    ]
    deteriorations = [
        row
        for row in primary
        if row["gate_vs_rank1_indicators"]["paired_negative_transfer"]
    ]
    conditions = [
        "no_memory",
        "tfidf_rank1_memory",
        "proper_gate_memory",
        "matched_applicable_memory",
    ]
    return {
        "schema_version": 1,
        "run_kind": "confirmatory_gate_v1_independent_analysis",
        "identities": {
            "raw_results_sha256": RAW_SHA256,
            "prepared_file_sha256": raw["identities"]["prepared_file_sha256"],
            "test_public_sha256": raw["identities"]["test_public_sha256"],
            "model_manifest_sha256": raw["identities"]["model_manifest_sha256"],
        },
        "population": {
            "all_valid_target_count": len(rows),
            "primary_gate_changed_count": len(primary),
            "gate_intervention_count": raw["screening"]["gate_intervention_count"],
            "gate_kept_applicable_rank1_count": sum(
                not row["gate_selection_changed"]
                and row["evaluator_only"]["rank1_applicable"]
                for row in rows
            ),
            "gate_kept_inapplicable_rank1_count": sum(
                not row["gate_selection_changed"]
                and not row["evaluator_only"]["rank1_applicable"]
                for row in rows
            ),
            "gate_changed_inapplicable_to_applicable_count": sum(
                row["gate_selection_changed"]
                and not row["evaluator_only"]["rank1_applicable"]
                and row["evaluator_only"]["gate_selected_applicable"]
                for row in rows
            ),
        },
        "primary_recomputed": recomputed_primary,
        "all_valid_targets_descriptive_pair": paired_metrics(rows),
        "condition_metrics_all_valid_targets": {
            condition: condition_metrics(rows, condition) for condition in conditions
        },
        "condition_metrics_primary_population": {
            condition: condition_metrics(primary, condition) for condition in conditions
        },
        "tool_strata_primary_population": tool_rows,
        "effect_concentration": {
            "improvement_count": len(improvements),
            "deterioration_count": len(deteriorations),
            "improvement_tool_counts": dict(
                sorted(
                    Counter(
                        row["failed_action"]["tool_name"] for row in improvements
                    ).items()
                )
            ),
            "improvement_selected_memory_counts": dict(
                sorted(
                    Counter(
                        row["gate_selected_experience_id"] for row in improvements
                    ).items()
                )
            ),
            "action_change_tool_counts": dict(
                sorted(
                    Counter(
                        row["failed_action"]["tool_name"]
                        for row in primary
                        if row["gate_vs_rank1_indicators"][
                            "memory_induced_action_change"
                        ]
                    ).items()
                )
            ),
            "all_improvements_single_tool": len(
                {row["failed_action"]["tool_name"] for row in improvements}
            )
            == 1,
            "all_improvements_single_selected_memory": len(
                {row["gate_selected_experience_id"] for row in improvements}
            )
            == 1,
        },
        "improvement_instance_ids": [row["instance_id"] for row in improvements],
        "model_output_parse_failure_count": raw["model_output_parse_failure_count"],
        "interpretation": {
            "preregistered_primary_hypothesis_supported": True,
            "claim_limited_to_argument_omission_extension": True,
            "cross_tool_causal_improvement_demonstrated": False,
            "reason": "all observed RV improvements and action changes occur on get_doc",
        },
    }


def main() -> int:
    analysis = run_analysis()
    OUTPUT.write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with TOOL_TABLE.open("w", encoding="utf-8", newline="") as handle:
        rows = analysis["tool_strata_primary_population"]
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(
        json.dumps(
            {
                "primary_recomputed": analysis["primary_recomputed"],
                "effect_concentration": analysis["effect_concentration"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    print("RESULT=PASS_CONFIRMATORY_GATE_V1_INDEPENDENT_ANALYSIS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
