"""CPU-only audit of whether the real branch acquisition runtime can be frozen."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/proper_v2_3/acquisition_runtime_feasibility_v2_3.json"
OUTPUT = ROOT / "outputs/proper_v2_3/acquisition_runtime_feasibility/audit.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate() -> dict[str, Any]:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    actual_hashes = {name: _sha256(ROOT / item["path"]) for name, item in config["inputs"].items()}
    expected_hashes = {name: item["sha256"] for name, item in config["inputs"].items()}
    worker_source = (ROOT / config["inputs"]["qwen_worker"]["path"]).read_text(encoding="utf-8")
    tau_config_source = (ROOT / "external/tau2-bench/src/tau2/config.py").read_text(encoding="utf-8")
    prior = json.loads((ROOT / config["inputs"]["prior_qwen_result"]["path"]).read_text(encoding="utf-8"))
    agent = config["known_agent_runtime"]
    user = config["user_simulator_runtime"]
    missing = config["missing_freezes"]
    runtime_ready = not missing and all((
        agent["worker_supports_tau_tool_messages"],
        agent["worker_supports_native_tool_call_objects"],
        agent["model_directory_manifest_frozen"],
        user["local_qwen_participant_adapter_implemented"],
        user["local_qwen_user_simulator_validated"],
        user["user_model_revision_frozen"],
    ))
    checks = {
        "all_input_hashes_match": actual_hashes == expected_hashes,
        "prior_qwen_agent_run_is_local_and_complete": prior["full_development_completed"] and prior["boundary"]["local_model_only"] and not prior["boundary"]["external_api_called"],
        "qwen_worker_is_text_role_only": 'role not in {"system", "user", "assistant"}' in worker_source and not agent["worker_supports_tau_tool_messages"],
        "qwen_worker_lacks_native_tool_objects": not agent["worker_supports_native_tool_call_objects"],
        "tau_default_user_model_is_external": user["tau_default_model"] in tau_config_source and user["tau_default_transport"] == "litellm_external_completion",
        "external_user_endpoint_is_not_frozen_or_authorized": not user["external_endpoint_frozen"] and not user["external_credentials_boundary_frozen"] and not config["boundary"]["external_api_authorized"],
        "local_user_adapter_is_not_implemented_or_validated": not user["local_qwen_participant_adapter_implemented"] and not user["local_qwen_user_simulator_validated"],
        "model_directory_revision_is_not_frozen": not agent["model_directory_manifest_frozen"] and not user["user_model_revision_frozen"],
        "missing_freezes_are_explicit": len(missing) == 7 and len(set(missing)) == len(missing),
        "runtime_correctly_stops_before_capture": not runtime_ready and config["disposition"] == "stop_before_acquisition_runtime_freeze",
        "task_model_gpu_gates_closed": not any((config["boundary"]["model_loading_authorized"], config["boundary"]["task_execution_authorized"], config["boundary"]["real_branch_capture_authorized"], config["boundary"]["gpu_authorized"], config["boundary"]["model_runner_authorized"])),
    }
    audit_passed = all(checks.values())
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_3_acquisition_runtime_feasibility_audit",
        "config_sha256": _sha256(CONFIG),
        "checks": checks,
        "audit_passed": audit_passed,
        "runtime_ready": runtime_ready,
        "missing_freezes": missing,
        "model_loaded": False,
        "model_outputs_read": False,
        "task_executed": False,
        "gpu_used": False,
        "participant_adapter_implementation_authorized": audit_passed,
        "acquisition_runtime_freeze_authorized": False,
        "real_branch_capture_authorized": False,
        "model_runner_authorized": False,
        "confirmatory_run_authorized": False,
        "next_gate": config["next_gate"],
    }


def main() -> int:
    result = validate()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["audit_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
