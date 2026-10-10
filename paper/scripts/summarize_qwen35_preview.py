#!/usr/bin/env python3
"""Summarize a development-only Qwen3.5 blind-audit preview CSV.

This script is deliberately separate from V1 human-review analysis.  It reports
schema validity, label completeness, and label distributions; it makes no claim
that machine labels are correct or suitable for human inter-annotator statistics.
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
DEFAULT_INPUT = ROOT / "paper/generated/qwen35_v1_preview_full.csv"
DEFAULT_OUTPUT = ROOT / "paper/generated/qwen35_v1_preview_summary.json"

LABEL_VALUES = {
    "decision_a_endpoint_label": {"true", "false"},
    "decision_b_endpoint_label": {"true", "false"},
    "decision_a_visible_support": {"supported", "unsupported", "unclear"},
    "decision_b_visible_support": {"supported", "unsupported", "unclear"},
    "confidence": {"high", "medium", "low"},
}
REQUIRED_FIELDS = {"pair_id", "failure_stratum", "notes", *LABEL_VALUES}


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


def summarize(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        missing = sorted(REQUIRED_FIELDS - set(fields))
        if missing:
            raise ValueError(f"input lacks required fields: {missing}")
        rows = list(reader)

    distributions = {field: Counter() for field in LABEL_VALUES}
    invalid_values: list[dict[str, str]] = []
    incomplete_pair_ids: list[str] = []
    strata = Counter(row["failure_stratum"].strip() for row in rows)
    for row in rows:
        complete = True
        for field, allowed in LABEL_VALUES.items():
            value = row[field].strip().lower()
            if not value:
                complete = False
                distributions[field]["<blank>"] += 1
            elif value not in allowed:
                complete = False
                distributions[field]["<invalid>"] += 1
                invalid_values.append({"pair_id": row["pair_id"], "field": field, "value": value})
            else:
                distributions[field][value] += 1
        if not complete:
            incomplete_pair_ids.append(row["pair_id"])

    return {
        "status": "development_only_machine_preview",
        "scope": "Schema and distribution check only; not V1 human review or formal evidence.",
        "input": root_relative(path),
        "input_sha256": sha256(path),
        "row_count": len(rows),
        "unique_pair_ids": len({row["pair_id"] for row in rows}),
        "strata": dict(sorted(strata.items())),
        "complete_label_rows": len(rows) - len(incomplete_pair_ids),
        "incomplete_label_rows": len(incomplete_pair_ids),
        "incomplete_pair_ids": incomplete_pair_ids,
        "invalid_value_count": len(invalid_values),
        "invalid_values": invalid_values,
        "label_distributions": {field: dict(sorted(counts.items())) for field, counts in distributions.items()},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    report = summarize(args.input.resolve())
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "rows": report["row_count"], "complete": report["complete_label_rows"], "output": root_relative(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
