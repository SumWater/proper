from __future__ import annotations

import argparse
import json
import sys
import unittest
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "proper_v2"))

import lifecycle_development_v2_2 as lifecycle  # noqa: E402
import toolsandbox_heldout_target_audit_v2_2 as heldout  # noqa: E402


def run_unit_tests() -> dict[str, Any]:
    suite = unittest.defaultTestLoader.discover(
        str(ROOT / "tests"),
        pattern="test_proper_v2_2*.py",
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return {
        "tests_run": result.testsRun,
        "failure_count": len(result.failures),
        "error_count": len(result.errors),
        "skipped_count": len(result.skipped),
        "passed": result.wasSuccessful(),
    }


def write_result(
    result: Mapping[str, Any],
    config: Mapping[str, Any],
) -> Path:
    output = ROOT / str(config["outputs"]["stage_validation"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return output


def validate_stage(*, static_only: bool) -> dict[str, Any]:
    config = lifecycle.load_config()
    unit = run_unit_tests()
    static = lifecycle.static_validation()
    lifecycle.write_result(static, config)
    heldout_config = heldout.load_config()
    audit = heldout.audit()
    heldout.write_result(audit, heldout_config)
    dynamic: dict[str, Any] | None = None
    if not static_only:
        import toolsandbox_lifecycle_development_v2_2 as toolsandbox

        dynamic = toolsandbox.dynamic_validation()
        toolsandbox.write_result(dynamic, config)
    checks = {
        "unit_tests_passed": unit["passed"],
        "static_lifecycle_validation_passed": static["passed"],
        "heldout_input_audit_passed": audit["audit_passed"],
        "heldout_confirmation_not_prematurely_authorized": not audit[
            "heldout_effect_validation_ready"
        ],
        "dynamic_toolsandbox_validation_passed": (
            None if static_only else bool(dynamic and dynamic["passed"])
        ),
    }
    required_checks = [
        value for value in checks.values() if value is not None
    ]
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_2_lifecycle_stage_validation",
        "mode": "static_only" if static_only else "full_toolsandbox",
        "checks": checks,
        "passed": all(required_checks),
        "unit_tests": unit,
        "static_lifecycle_summary": static["summary"],
        "dynamic_lifecycle_summary": (
            dynamic["summary"] if dynamic is not None else None
        ),
        "heldout_audit_summary": audit["summary"],
        "heldout_effect_validation_ready": audit[
            "heldout_effect_validation_ready"
        ],
        "next_heldout_action": audit["next_action"],
        "boundary": {
            "model_loaded": False,
            "model_outputs_read": False,
            "gpu_run_authorized": False,
            "confirmatory_claim_authorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="One-shot validation entry for the PROPER v2.2 lifecycle stage."
    )
    parser.add_argument(
        "--static-only",
        action="store_true",
        help="Skip ToolSandbox execution; useful outside the remote conda env.",
    )
    args = parser.parse_args()
    config = lifecycle.load_config()
    result = validate_stage(static_only=args.static_only)
    output = write_result(result, config)
    print(
        json.dumps(
            {
                "mode": result["mode"],
                "checks": result["checks"],
                "static_lifecycle_summary": result[
                    "static_lifecycle_summary"
                ],
                "dynamic_lifecycle_summary": result[
                    "dynamic_lifecycle_summary"
                ],
                "heldout_audit_summary": result["heldout_audit_summary"],
                "heldout_effect_validation_ready": result[
                    "heldout_effect_validation_ready"
                ],
                "next_heldout_action": result["next_heldout_action"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    print(f"OUTPUT={output}")
    status = "PASS" if result["passed"] else "STOP"
    print(f"RESULT={status}_PROPER_V2_2_LIFECYCLE_STAGE")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
