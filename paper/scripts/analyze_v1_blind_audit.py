#!/usr/bin/env python3
"""Analyze independent human Reviewer A/B V1 audit CSVs after they are completed.

It never reads the sealed identity key or a Qwen preview. With incomplete human
labels it writes a coverage report only; agreement and evaluator comparisons are
computed only for jointly completed labels.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PACKET = ROOT / "outputs/paper_2026/evaluator_blind_audit/reviewer_packet"
DEFAULT_A = PACKET / "reviewer_a.csv"
DEFAULT_B = PACKET / "reviewer_b.csv"
DEFAULT_OUTPUT = ROOT / "paper/generated/v1_blind_audit_report.json"
DEFAULT_DISAGREEMENTS = ROOT / "paper/generated/v1_blind_audit_disagreements.csv"

LABEL_FIELDS = (
    "decision_a_endpoint_label",
    "decision_b_endpoint_label",
    "decision_a_visible_support",
    "decision_b_visible_support",
    "confidence",
)
LABEL_VALUES = {
    "decision_a_endpoint_label": {"true", "false"},
    "decision_b_endpoint_label": {"true", "false"},
    "decision_a_visible_support": {"supported", "unsupported", "unclear"},
    "decision_b_visible_support": {"supported", "unsupported", "unclear"},
    "confidence": {"high", "medium", "low"},
}
REQUIRED_FIELDS = {"pair_id", "failure_stratum", "notes", *LABEL_FIELDS}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def root_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def load_reviewer(path: Path) -> tuple[dict[str, dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        missing = sorted(REQUIRED_FIELDS - set(fields))
        if missing:
            raise ValueError(f"{path.name} lacks required fields: {missing}")
        rows = list(reader)
    indexed: dict[str, dict[str, str]] = {}
    duplicates: list[str] = []
    for row in rows:
        pair_id = row["pair_id"].strip()
        if pair_id in indexed:
            duplicates.append(pair_id)
        indexed[pair_id] = {key: (value or "").strip().lower() for key, value in row.items()}
    return indexed, duplicates


def completed(value: str, field: str) -> bool:
    return value in LABEL_VALUES[field]


def cohen_kappa(pairs: list[tuple[str, str]]) -> float | None:
    """Unweighted Cohen's kappa; return None where chance agreement is undefined."""
    if not pairs:
        return None
    n = len(pairs)
    observed = sum(left == right for left, right in pairs) / n
    left_counts = Counter(left for left, _ in pairs)
    right_counts = Counter(right for _, right in pairs)
    expected = sum((left_counts[label] / n) * (right_counts[label] / n) for label in set(left_counts) | set(right_counts))
    if expected == 1:
        return None
    return (observed - expected) / (1 - expected)


def auto_endpoint(row: dict[str, str], decision: str) -> str:
    """Frozen endpoint reproduced from visible packet fields; no sealed key needed."""
    prefix = f"decision_{decision}_"
    parse_valid = row.get(prefix + "parse_valid", "").strip().lower() == "true"
    no_second_error = not row.get(prefix + "second_error_code", "").strip()
    complete_task = row.get(prefix + "task_completion", "").strip().lower() == "true"
    no_safety_violation = row.get(prefix + "safety_violation", "").strip().lower() == "false"
    return "true" if parse_valid and no_second_error and complete_task and no_safety_violation else "false"


def agreement_summary(pairs: list[tuple[str, str]]) -> dict[str, Any]:
    if not pairs:
        return {"jointly_labeled": 0, "exact_agreement": None, "cohen_kappa": None}
    return {
        "jointly_labeled": len(pairs),
        "exact_agreement": sum(left == right for left, right in pairs) / len(pairs),
        "cohen_kappa": cohen_kappa(pairs),
        "reviewer_a_distribution": dict(sorted(Counter(left for left, _ in pairs).items())),
        "reviewer_b_distribution": dict(sorted(Counter(right for _, right in pairs).items())),
    }


def evaluator_comparison(rows: dict[str, dict[str, str]], field: str) -> dict[str, Any]:
    decision = "a" if field.startswith("decision_a_") else "b"
    pairs = [(row[field], auto_endpoint(row, decision)) for row in rows.values() if completed(row[field], field)]
    if not pairs:
        return {"labeled": 0, "agreement": None, "confusion": {}}
    confusion = Counter(f"human_{human}__auto_{automatic}" for human, automatic in pairs)
    return {
        "labeled": len(pairs),
        "agreement": sum(human == automatic for human, automatic in pairs) / len(pairs),
        "confusion": dict(sorted(confusion.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviewer-a", type=Path, default=DEFAULT_A)
    parser.add_argument("--reviewer-b", type=Path, default=DEFAULT_B)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--disagreements-output", type=Path, default=DEFAULT_DISAGREEMENTS)
    args = parser.parse_args()

    a_path, b_path = args.reviewer_a.resolve(), args.reviewer_b.resolve()
    sealed_directory = ROOT / "outputs/paper_2026/evaluator_blind_audit/sealed_key"
    if sealed_directory in a_path.parents or sealed_directory in b_path.parents:
        raise RuntimeError("sealed key must never be used as an audit input")
    reviewer_a, duplicate_a = load_reviewer(a_path)
    reviewer_b, duplicate_b = load_reviewer(b_path)
    ids_a, ids_b = set(reviewer_a), set(reviewer_b)
    common_ids = sorted(ids_a & ids_b)

    coverage: dict[str, dict[str, int]] = {}
    agreements: dict[str, dict[str, Any]] = {}
    disagreements: list[dict[str, str]] = []
    for field in LABEL_FIELDS:
        a_labeled = sum(completed(row[field], field) for row in reviewer_a.values())
        b_labeled = sum(completed(row[field], field) for row in reviewer_b.values())
        pairs = [(reviewer_a[pair_id][field], reviewer_b[pair_id][field]) for pair_id in common_ids if completed(reviewer_a[pair_id][field], field) and completed(reviewer_b[pair_id][field], field)]
        coverage[field] = {"reviewer_a_labeled": a_labeled, "reviewer_b_labeled": b_labeled, "jointly_labeled": len(pairs)}
        agreements[field] = agreement_summary(pairs)
        for pair_id, pair in zip([pair_id for pair_id in common_ids if completed(reviewer_a[pair_id][field], field) and completed(reviewer_b[pair_id][field], field)], pairs):
            if pair[0] != pair[1]:
                disagreements.append({"pair_id": pair_id, "failure_stratum": reviewer_a[pair_id]["failure_stratum"], "field": field, "reviewer_a": pair[0], "reviewer_b": pair[1]})

    fully_completed = bool(common_ids) and all(item["jointly_labeled"] == len(common_ids) for item in coverage.values())
    report = {
        "status": "complete_human_double_blind" if fully_completed else "incomplete_human_labels_no_formal_v1_conclusion",
        "scope": "Human Reviewer A/B agreement and comparison against the frozen automated endpoint only. Qwen previews are excluded.",
        "inputs": {"reviewer_a": root_relative(a_path), "reviewer_a_sha256": sha256(a_path), "reviewer_b": root_relative(b_path), "reviewer_b_sha256": sha256(b_path)},
        "pair_alignment": {"reviewer_a_rows": len(reviewer_a), "reviewer_b_rows": len(reviewer_b), "common_pair_ids": len(common_ids), "only_in_a": sorted(ids_a - ids_b), "only_in_b": sorted(ids_b - ids_a), "duplicate_ids_a": duplicate_a, "duplicate_ids_b": duplicate_b},
        "coverage": coverage,
        "agreement": agreements,
        "endpoint_vs_frozen_automatic_evaluator": {"reviewer_a": {field: evaluator_comparison(reviewer_a, field) for field in ("decision_a_endpoint_label", "decision_b_endpoint_label")}, "reviewer_b": {field: evaluator_comparison(reviewer_b, field) for field in ("decision_a_endpoint_label", "decision_b_endpoint_label")}},
        "disagreement_count": len(disagreements),
        "interpretation_guard": "Do not report a formal V1 reliability conclusion unless status is complete_human_double_blind and reviewer files have been finalized and hash-locked.",
    }

    disagreements_path = args.disagreements_output.resolve()
    disagreements_path.parent.mkdir(parents=True, exist_ok=True)
    with disagreements_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["pair_id", "failure_stratum", "field", "reviewer_a", "reviewer_b"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(disagreements)
    output_path = args.output.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "common_pairs": len(common_ids), "disagreements": len(disagreements), "output": root_relative(output_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
