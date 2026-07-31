from __future__ import annotations

import argparse
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "proper_v2"))
sys.path.insert(0, str(ROOT / "tests"))

import toolsandbox_continuation_target_inventory_v2_2_1 as inventory  # noqa: E402
import toolsandbox_qwen_continuation_development_v2_2_1 as qwen  # noqa: E402


TEST_MODULES = (
    "test_proper_v2_2_1_continuation",
    "test_proper_v2_2_development",
    "test_proper_v2_2_lifecycle",
    "test_proper_v2_2_unconsumed_capacity",
    "test_proper_v2_boundary",
    "test_proper_v2_policy_extraction",
    "test_proper_v2_selector",
    "test_toolsandbox_continuation_conditions_preparation_v2_2_1",
    "test_toolsandbox_continuation_development_v2_2_1",
    "test_toolsandbox_continuation_target_inventory_v2_2_1",
    "test_toolsandbox_qwen_continuation_development_v2_2_1",
    "test_toolsandbox_feasibility",
    "test_toolsandbox_model_pilot_preparation_v2_1",
    "test_toolsandbox_model_pilot_runner_validation_v2_1",
    "test_toolsandbox_qwen_pilot_v2_1",
)


def run_unit_tests() -> unittest.result.TestResult:
    suite = unittest.defaultTestLoader.loadTestsFromNames(TEST_MODULES)
    return unittest.TextTestRunner(verbosity=2).run(suite)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run prospective target inventory, scripted ToolSandbox validation, "
            "and Qwen continuation development in one guarded stage."
        )
    )
    parser.add_argument(
        "--inventory-config",
        type=Path,
        default=inventory.CONFIG,
    )
    parser.add_argument(
        "--qwen-config",
        type=Path,
        default=qwen.CONFIG,
    )
    args = parser.parse_args()

    print("STAGE=unit_tests", flush=True)
    test_result = run_unit_tests()
    if not test_result.wasSuccessful():
        print("RESULT=STOP_CONTINUATION_STAGE_UNIT_TESTS", flush=True)
        return 1

    print("STAGE=prospective_target_inventory", flush=True)
    inventory_config = inventory.load_config(args.inventory_config)
    inventory_result = inventory.inventory(args.inventory_config)
    inventory_output = inventory.write_result(
        inventory_result,
        inventory_config,
    )
    print(
        json.dumps(
            inventory_result["summary"],
            ensure_ascii=False,
            sort_keys=True,
        ),
        flush=True,
    )
    print(f"INVENTORY_OUTPUT={inventory_output}", flush=True)

    print("STAGE=qwen_continuation_development", flush=True)
    qwen_config = qwen.load_config(args.qwen_config)
    qwen_result = qwen.run_development(args.qwen_config)
    qwen_output = ROOT / str(qwen_config["output"]["path"])
    qwen_output.parent.mkdir(parents=True, exist_ok=True)
    qwen_output.write_text(
        json.dumps(
            qwen_result,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "run_kind": qwen_result["run_kind"],
                "smoke_passed": qwen_result["smoke_passed"],
                "full_development_completed": qwen_result[
                    "full_development_completed"
                ],
                "summary": qwen_result.get("summary"),
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        flush=True,
    )
    print(f"QWEN_OUTPUT={qwen_output}", flush=True)
    status = bool(qwen_result.get("full_development_completed"))
    print(
        "RESULT="
        + (
            "PASS_PROPER_V2_2_1_CONTINUATION_STAGE"
            if status
            else "STOP_PROPER_V2_2_1_CONTINUATION_STAGE"
        ),
        flush=True,
    )
    return 0 if status else 1


if __name__ == "__main__":
    raise SystemExit(main())
