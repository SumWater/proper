"""CPU-only local validation of the remote read-only inventory entry."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/proper_v2_3/qwen_model_inventory_v2_3.json"
SCHEMA = ROOT / "schemas/proper_v2_3/qwen_model_inventory.schema.json"
RUNNER = ROOT / "experiments/proper_v2_3/run_qwen_model_inventory_remote_v2_3.py"
OUTPUT = ROOT / "outputs/proper_v2_3/qwen_model_inventory_preparation/validation.json"
INPUTS = (
    "configs/proper_v2_3/qwen_model_inventory_v2_3.json",
    "experiments/proper_v2_3/run_qwen_model_inventory_remote_v2_3.py",
    "schemas/proper_v2_3/qwen_model_inventory.schema.json",
    "src/failure_memory/proper_v2/v2_3/model_inventory.py",
    "tests/test_proper_v2_3_qwen_model_inventory.py",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def validate() -> dict[str, Any]:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    tests = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_proper_v2_3_qwen_model_inventory"],
        cwd=ROOT, capture_output=True, text=True,
    )
    imports = _imports(RUNNER) | _imports(ROOT / "src/failure_memory/proper_v2/v2_3/model_inventory.py")
    forbidden_imports = sorted(imports & {"torch", "transformers", "accelerate", "tau2"})
    hashes = {relative: _sha256(ROOT / relative) for relative in INPUTS}
    boundary = config["boundary"]
    skipped_match = re.search(r"skipped=(\d+)", tests.stderr)
    skipped = int(skipped_match.group(1)) if skipped_match else 0
    checks = {
        "inventory_test_module_passes": tests.returncode == 0,
        "all_stage_inputs_hashed": len(hashes) == len(INPUTS),
        "schema_is_closed": schema.get("additionalProperties") is False,
        "failure_results_are_serializable": "stop_reason" in schema["required"],
        "model_root_is_absolute": PurePosixPath(config["model_root"]).is_absolute(),
        "symlinks_stop_closed": not config["hash_contract"]["follow_symlinks"],
        "no_model_or_tau_imports": not forbidden_imports,
        "model_task_gpu_gates_closed": not any((
            boundary["import_model_libraries"], boundary["load_model"],
            boundary["read_model_outputs"], boundary["execute_tau_task"], boundary["use_gpu"],
        )),
    }
    passed = all(checks.values())
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_3_qwen_model_inventory_preparation_validation",
        "checks": checks,
        "passed": passed,
        "stage_input_sha256": hashes,
        "scoped_tests_run": 6,
        "scoped_tests_skipped": skipped,
        "model_loaded": False,
        "model_outputs_read": False,
        "task_executed": False,
        "gpu_used": False,
        "remote_read_only_inventory_authorized": passed,
        "acquisition_runtime_freeze_authorized": False,
        "real_branch_capture_authorized": False,
        "model_runner_authorized": False,
        "confirmatory_run_authorized": False,
        "next_gate": "run_remote_read_only_qwen_model_inventory" if passed else "stop_inventory_preparation",
    }


def main() -> int:
    result = validate()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
