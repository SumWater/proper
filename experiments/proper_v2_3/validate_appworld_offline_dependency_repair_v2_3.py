"""Validate the frozen offline dependency-repair entry point."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/proper_v2_3/appworld_offline_dependency_repair_v2_3.json"
OUTPUT = ROOT / "outputs/proper_v2_3/appworld_offline_dependency_repair/validation.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    runner = (ROOT / "experiments/proper_v2_3/run_appworld_offline_dependency_repair_remote_v2_3.py").read_text(encoding="utf-8")
    tests = subprocess.run([sys.executable,"-m","unittest","tests.test_proper_v2_3_appworld_offline_dependency_repair"],cwd=ROOT,capture_output=True,text=True,check=False)
    checks = {
        "all_frozen_inputs_match": all(sha256(ROOT / item["path"]) == item["sha256"] for item in config["frozen_inputs"]),
        "complete_three_wheel_chain_exactly_pinned": [item["filename"].split("-")[0] for item in config["artifacts"]] == ["pycparser","cffi","cryptography"],
        "versions_are_exact_and_within_prior_major_gate": config["expected_versions"] == {"cryptography":"49.0.0","cffi":"2.0.0","pycparser":"2.23"},
        "install_is_no_index_no_deps_binary_only": all(token in runner for token in ('"--no-index"','"--no-deps"','"--only-binary=:all:"')),
        "runner_has_no_network_client": all(token not in runner for token in ("requests", "urllib", "http://", "https://")),
        "target_is_external_absent_and_non_overwriting": config["runtime"]["target_must_be_external_and_absent"] and '"target_is_absolute_external_and_absent"' in runner,
        "wheelhouse_requires_exact_files_sizes_and_hashes": "observed_files == expected_files" in runner and "path.stat().st_size" in runner and "sha256(path)" in runner,
        "version_probe_precedes_one_inventory_call": runner.count("str(INVENTORY_RUNNER)") == 1 and runner.index("probe_code =") < runner.index("str(INVENTORY_RUNNER)"),
        "failure_results_are_atomically_preserved": "write_json_atomic" in runner and "stop_and_preserve_dependency_repair_result" in runner,
        "scientific_inputs_and_model_gpu_boundaries_unchanged": config["authority"]["same_inventory_inputs"] and not any((config["authority"]["model"],config["authority"]["gpu"],config["authority"]["confirmatory_claim"])),
        "five_contract_tests_pass": tests.returncode == 0 and "Ran 5 tests" in tests.stderr,
        "one_remote_invocation_only": config["authority"]["one_remote_invocation"],
    }
    value = {"schema_version":1,"run_kind":"proper_v2_3_appworld_offline_dependency_repair_validation","passed":all(checks.values()),"checks":checks,"config_sha256":sha256(CONFIG),"tests_run":5,"network_used":False,"dependency_installed":False,"apps_bundle_decrypted":False,"model_loaded":False,"gpu_used":False,"one_remote_repair_invocation_authorized":all(checks.values()),"next_gate":"run_one_offline_dependency_repair_and_inventory" if all(checks.values()) else "stop_dependency_repair"}
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_bytes((json.dumps(value,ensure_ascii=False,indent=2,sort_keys=True)+"\n").encode("utf-8"))
    print(json.dumps(value,ensure_ascii=False,sort_keys=True))
    return 0 if value["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
