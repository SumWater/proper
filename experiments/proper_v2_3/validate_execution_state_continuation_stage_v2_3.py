"""One-shot CPU validation for the execution-state continuation design stage."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from planbench_xl_capacity_audit_v2_3 import validate_planbench_xl_audit_design
from scripted_continuation_traces_v2_3 import run_scripted_continuation_traces

ROOT = Path(__file__).resolve().parents[2]

STAGE_INPUTS = (
    "configs/proper_v2_3/execution_state_continuation_design_v2_3.json",
    "configs/proper_v2_3/planbench_xl_capacity_audit_design_v2_3.json",
    "docs/proper_v2_3/execution_state_continuation_design.md",
    "docs/proper_v2_3/execution_state_continuation_stage_result.md",
    "docs/proper_v2_3/planbench_xl_capacity_audit_design.md",
    "experiments/proper_v2_3/planbench_xl_capacity_audit_v2_3.py",
    "experiments/proper_v2_3/scripted_continuation_traces_v2_3.py",
    "schemas/proper_v2_3/continuation_decision.schema.json",
    "schemas/proper_v2_3/execution_progress_state.schema.json",
    "schemas/proper_v2_3/planbench_xl_capacity_audit_design.schema.json",
    "src/failure_memory/proper_v2/v2_3/continuation.py",
    "tests/test_proper_v2_3_execution_state_continuation.py",
    "tests/test_proper_v2_3_planbench_xl_capacity_audit.py",
    "tests/test_toolsandbox_v2_3_continuation_traces.py",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_stage() -> dict[str, Any]:
    trace_result = run_scripted_continuation_traces()
    capacity_result = validate_planbench_xl_audit_design()
    schemas = {}
    for relative in (
        "schemas/proper_v2_3/continuation_decision.schema.json",
        "schemas/proper_v2_3/execution_progress_state.schema.json",
        "schemas/proper_v2_3/planbench_xl_capacity_audit_design.schema.json",
    ):
        schema = json.loads((ROOT / relative).read_text(encoding="utf-8"))
        schemas[relative] = (
            schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
            and schema.get("additionalProperties") is False
        )
    hashes = {relative: _sha256(ROOT / relative) for relative in STAGE_INPUTS}
    checks = {
        "scripted_continuation_traces_pass": trace_result["passed"],
        "planbench_design_validation_passes": capacity_result["passed"],
        "planbench_stops_before_unfrozen_inventory": capacity_result["disposition"]
        == "stop_before_inventory",
        "closed_draft_2020_12_schemas": all(schemas.values()),
        "all_stage_inputs_hashed": len(hashes) == len(STAGE_INPUTS),
    }
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_3_execution_state_continuation_stage_validation",
        "checks": checks,
        "passed": all(checks.values()),
        "scripted_trace_count": trace_result["trace_count"],
        "stage_input_sha256": hashes,
        "model_loaded": False,
        "model_outputs_read": False,
        "gpu_used": False,
        "existing_12_pairs_rerun": False,
        "model_run_authorized": False,
        "confirmatory_run_authorized": False,
        "next_gate": "freeze_external_source_revision_before_capacity_inventory",
    }


def main() -> int:
    result = validate_stage()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
