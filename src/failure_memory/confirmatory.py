"""Frozen confirmatory-v2 action and paired-outcome measurements."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping, Sequence

from .utilization import AgentDecision, DecisionKind


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def decision_payload(decision: AgentDecision) -> dict[str, Any]:
    if decision.kind == DecisionKind.TOOL:
        return {
            "kind": "tool",
            "tool_name": decision.tool_name,
            "args": dict(decision.args),
        }
    return {"kind": "stop", "reason_code": decision.reason_code}


def canonicalize_decision(decision: AgentDecision) -> str:
    return canonical_json(decision_payload(decision))


def _flatten(value: Any, path: str = "") -> dict[str, str]:
    if isinstance(value, Mapping):
        if not value:
            return {path: "{}"} if path else {}
        flattened: dict[str, str] = {}
        for key in sorted(value, key=str):
            escaped = str(key).replace("~", "~0").replace("/", "~1")
            flattened.update(_flatten(value[key], f"{path}/{escaped}"))
        return flattened
    return {path or "/": canonical_json(value)}


@dataclass(frozen=True)
class ArgumentDiff:
    added: tuple[str, ...]
    removed: tuple[str, ...]
    replaced: tuple[str, ...]
    renamed: tuple[tuple[str, str], ...]


def argument_diff(before: Mapping[str, Any], after: Mapping[str, Any]) -> ArgumentDiff:
    left = _flatten(before)
    right = _flatten(after)
    added = tuple(sorted(right.keys() - left.keys()))
    removed = tuple(sorted(left.keys() - right.keys()))
    replaced = tuple(
        sorted(path for path in left.keys() & right.keys() if left[path] != right[path])
    )

    rename_candidates: list[tuple[str, str]] = []
    used_added: set[str] = set()
    for old_path in removed:
        matches = [
            new_path
            for new_path in added
            if new_path not in used_added and left[old_path] == right[new_path]
        ]
        if len(matches) == 1:
            new_path = matches[0]
            rename_candidates.append((old_path, new_path))
            used_added.add(new_path)
    return ArgumentDiff(added, removed, replaced, tuple(rename_candidates))


def _tool_action_payload(action: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "kind": "tool",
        "tool_name": action.get("tool_name"),
        "args": dict(action.get("args", {})),
    }


def behavior_atoms(
    *,
    failed_action: Mapping[str, Any],
    no_memory_decision: AgentDecision,
    condition_decision: AgentDecision,
    schema_verification_tools: Iterable[str] = (),
) -> dict[str, Any]:
    """Return predeclared observable behavior atoms without semantic judging."""

    failed = _tool_action_payload(failed_action)
    candidate = decision_payload(condition_decision)
    no_memory = decision_payload(no_memory_decision)
    verification_tools = frozenset(schema_verification_tools)

    if condition_decision.kind == DecisionKind.TOOL:
        failed_diff = argument_diff(failed["args"], candidate["args"])
        no_memory_args = no_memory.get("args", {}) if no_memory.get("kind") == "tool" else {}
        paired_diff = argument_diff(no_memory_args, candidate["args"])
    else:
        failed_diff = argument_diff(failed["args"], {})
        paired_diff = argument_diff(no_memory.get("args", {}), {})

    same_tool = (
        condition_decision.kind == DecisionKind.TOOL
        and condition_decision.tool_name == failed["tool_name"]
    )
    return {
        "same_tool": same_tool,
        "exact_retry": canonical_json(candidate) == canonical_json(failed),
        "argument_add": list(failed_diff.added),
        "argument_remove": list(failed_diff.removed),
        "argument_replace": list(failed_diff.replaced),
        "argument_rename": [list(pair) for pair in failed_diff.renamed],
        "stop": condition_decision.kind == DecisionKind.STOP,
        "fallback": (
            condition_decision.kind == DecisionKind.TOOL
            and condition_decision.tool_name != failed["tool_name"]
        ),
        "verify_schema": (
            condition_decision.kind == DecisionKind.TOOL
            and condition_decision.tool_name in verification_tools
        ),
        "different_from_no_memory": canonical_json(candidate) != canonical_json(no_memory),
        "paired_argument_add": list(paired_diff.added),
        "paired_argument_remove": list(paired_diff.removed),
        "paired_argument_replace": list(paired_diff.replaced),
        "paired_argument_rename": [list(pair) for pair in paired_diff.renamed],
    }


@dataclass(frozen=True)
class PairIndicators:
    paired_negative_transfer: bool
    paired_positive_transfer: bool
    memory_induced_action_change: bool
    inapplicable_memory_harm: bool
    strict_policy_adoption: bool
    policy_followed_harm: bool


def pair_indicators(
    *,
    no_memory_recovery_validity: bool,
    memory_recovery_validity: bool,
    no_memory_decision: AgentDecision,
    memory_decision: AgentDecision,
    strict_policy_adoption: bool,
) -> PairIndicators:
    pnt = no_memory_recovery_validity and not memory_recovery_validity
    ppt = memory_recovery_validity and not no_memory_recovery_validity
    miac = canonicalize_decision(no_memory_decision) != canonicalize_decision(memory_decision)
    return PairIndicators(
        paired_negative_transfer=pnt,
        paired_positive_transfer=ppt,
        memory_induced_action_change=miac,
        inapplicable_memory_harm=miac and pnt,
        strict_policy_adoption=strict_policy_adoption,
        policy_followed_harm=strict_policy_adoption and pnt,
    )


def exact_mcnemar_two_sided(pnt_count: int, ppt_count: int) -> float:
    if min(pnt_count, ppt_count) < 0:
        raise ValueError("discordant counts must be non-negative")
    discordant = pnt_count + ppt_count
    if discordant == 0:
        return 1.0
    tail = min(pnt_count, ppt_count)
    cumulative = sum(math.comb(discordant, index) for index in range(tail + 1))
    return min(1.0, 2.0 * cumulative / (2**discordant))


def paired_wald_interval(
    no_memory: Sequence[bool],
    memory: Sequence[bool],
    *,
    confidence_z: float = 1.959963984540054,
) -> tuple[float, float, float]:
    """Paired normal interval for risk difference E[R_memory - R_no_memory]."""

    if len(no_memory) != len(memory) or not no_memory:
        raise ValueError("paired non-empty outcome sequences are required")
    differences = [int(current) - int(baseline) for baseline, current in zip(no_memory, memory)]
    count = len(differences)
    mean = sum(differences) / count
    if count == 1:
        return mean, mean, mean
    variance = sum((value - mean) ** 2 for value in differences) / (count - 1)
    margin = confidence_z * math.sqrt(variance / count)
    return mean, max(-1.0, mean - margin), min(1.0, mean + margin)


def aggregate_pair_indicators(
    indicators: Sequence[PairIndicators],
    no_memory: Sequence[bool],
    memory: Sequence[bool],
    *,
    alpha: float = 0.05,
) -> dict[str, Any]:
    if len(indicators) != len(no_memory) or len(no_memory) != len(memory):
        raise ValueError("indicator and outcome lengths must match")
    count = len(indicators)
    if count == 0:
        raise ValueError("at least one pair is required")
    pnt = sum(item.paired_negative_transfer for item in indicators)
    ppt = sum(item.paired_positive_transfer for item in indicators)
    risk_difference, lower, upper = paired_wald_interval(no_memory, memory)
    p_value = exact_mcnemar_two_sided(pnt, ppt)
    return {
        "pair_count": count,
        "paired_negative_transfer_count": pnt,
        "paired_negative_transfer_rate": pnt / count,
        "paired_positive_transfer_count": ppt,
        "paired_positive_transfer_rate": ppt / count,
        "net_paired_effect": risk_difference,
        "paired_risk_difference": risk_difference,
        "paired_risk_difference_ci95": [lower, upper],
        "paired_risk_difference_ci_method": "paired_wald_normal_clipped",
        "exact_mcnemar_two_sided_p": p_value,
        "directional_hypothesis_supported": pnt > ppt and p_value < alpha,
        "memory_induced_action_change_count": sum(
            item.memory_induced_action_change for item in indicators
        ),
        "inapplicable_memory_harm_count": sum(
            item.inapplicable_memory_harm for item in indicators
        ),
        "strict_policy_adoption_count": sum(item.strict_policy_adoption for item in indicators),
        "policy_followed_harm_count": sum(item.policy_followed_harm for item in indicators),
    }


def indicators_payload(indicators: PairIndicators) -> dict[str, bool]:
    return asdict(indicators)
