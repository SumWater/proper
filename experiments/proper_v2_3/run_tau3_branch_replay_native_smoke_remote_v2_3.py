"""One-shot remote CPU smoke for the tau3 split-state replay adapter."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import types
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/proper_v2_3/tau3_branch_replay_native_smoke_v2_3.json"
SCHEMA = ROOT / "schemas/proper_v2_3/tau3_branch_replay_native_smoke.schema.json"
TAU_SOURCE = ROOT / "external/tau2-bench/src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TAU_SOURCE) not in sys.path:
    sys.path.insert(0, str(TAU_SOURCE))

from src.failure_memory.proper_v2.v2_3.branch_capture import PublicBranchCapture, canonical_sha256
from src.failure_memory.proper_v2.v2_3.branch_replay_adapter import (
    SplitStateEnvironmentAdapter,
    make_tau_checkpoint_exporter,
    tau_initialization_data_builder,
)


def _install_lightweight_tau_source_namespace() -> None:
    """Load required tau source modules without importing the unused batch runner."""

    if "tau2" in sys.modules:
        raise RuntimeError("tau2 was imported before the lightweight source namespace guard")
    package_directory = TAU_SOURCE / "tau2"
    package = types.ModuleType("tau2")
    package.__file__ = str(package_directory / "__init__.py")
    package.__package__ = "tau2"
    package.__path__ = [str(package_directory)]
    sys.modules["tau2"] = package


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(expected_project_revision: str) -> dict[str, Any]:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    project_revision = _git("rev-parse", "HEAD")
    status = _git("status", "--porcelain", "--untracked-files=no")
    tau_directory = ROOT / config["source"]["directory"]
    tau_revision = subprocess.run(
        ["git", "-C", str(tau_directory), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    allowed_minors = config["source"]["allowed_python_minors"]
    if sys.version_info.major != config["source"]["python_major"] or sys.version_info.minor not in allowed_minors:
        allowed = ", ".join(f"3.{minor}" for minor in allowed_minors)
        raise RuntimeError(f"Python {allowed} is required, got {sys.version.split()[0]}")
    if project_revision != expected_project_revision:
        raise RuntimeError(f"project revision mismatch: {project_revision} != {expected_project_revision}")
    if status:
        raise RuntimeError("tracked project worktree must be clean")
    if tau_revision != config["source"]["revision"]:
        raise RuntimeError(f"tau3 revision mismatch: {tau_revision}")

    _install_lightweight_tau_source_namespace()
    from tau2.domains.retail.environment import get_environment

    source_environment = get_environment()
    pending = sorted(
        order_id for order_id, order in source_environment.tools.db.orders.items()
        if order.status == "pending"
    )
    if not pending:
        raise RuntimeError("no pending retail order is available for isolated smoke")
    order_id = pending[0]
    native_execution_count = 0
    source_environment.make_tool_call(
        config["fixture"]["native_action"], order_id=order_id,
        reason=config["fixture"]["arguments"]["reason"],
    )
    native_execution_count += 1
    checkpoint = {"agent_data": source_environment.tools.db.model_dump()}
    capture = PublicBranchCapture(
        public_history=(
            {"role": "user", "content": "Cancel the selected pending order after confirmation."},
            {"role": "assistant", "tool_calls": [{"id": "native-effect-1", "name": "cancel_pending_order", "arguments": {"order_id": order_id, "reason": config["fixture"]["arguments"]["reason"]}}]},
            {"role": "tool", "tool_call_id": "native-effect-1", "content": {"code": "result_unknown"}, "error": True, "outcome": "unknown"},
        ),
        effect_class="non_idempotent_side_effect", receipt_kind="outcome_unknown",
        guarded_call_id="native-effect-1", native_execution_observed=True,
        checkpoint_payload=checkpoint, checkpoint_applied_call_ids=("native-effect-1",),
        controller_state={"ledger": [{"call_id": "native-effect-1", "outcome": "unknown"}]},
    )
    replay_environment = get_environment()
    plan = capture.replay_plan()
    adapter = SplitStateEnvironmentAdapter(
        replay_environment, plan,
        checkpoint_builder=tau_initialization_data_builder,
        checkpoint_exporter=make_tau_checkpoint_exporter(checkpoint),
    )
    adapter.set_state(None, None, list(capture.public_history))
    restored_checkpoint = {"agent_data": replay_environment.tools.db.model_dump()}
    checks = {
        "project_revision_matches": project_revision == expected_project_revision,
        "project_worktree_clean": status == "",
        "tau3_revision_matches": tau_revision == config["source"]["revision"],
        "pending_order_cancelled_before_capture": source_environment.tools.db.orders[order_id].status == config["fixture"]["expected_restored_status"],
        "restored_order_status_matches": replay_environment.tools.db.orders[order_id].status == config["fixture"]["expected_restored_status"],
        "checkpoint_hash_matches": canonical_sha256(restored_checkpoint) == capture.checkpoint_sha256,
        "environment_replay_history_empty": plan["environment_replay_history"] == [],
        "native_execution_count_is_one": native_execution_count == config["fixture"]["expected_native_execution_count"],
        "adapter_initialized_once": adapter.initialized,
    }
    passed = all(checks.values())
    return {
        "schema_version": 1,
        "run_kind": "proper_v2_3_tau3_branch_replay_native_cpu_smoke",
        "project_revision": project_revision,
        "tau3_revision": tau_revision,
        "config_sha256": _sha256(CONFIG),
        "checks": checks,
        "passed": passed,
        "selected_order_id_sha256": canonical_sha256(order_id),
        "native_execution_count": native_execution_count,
        "checkpoint_sha256": capture.checkpoint_sha256,
        "restored_checkpoint_sha256": canonical_sha256(restored_checkpoint),
        "task_loaded": False,
        "model_loaded": False,
        "model_outputs_read": False,
        "gpu_used": False,
        "real_branch_capture_authorized": passed,
        "model_runner_authorized": False,
        "model_run_authorized": False,
        "confirmatory_run_authorized": False,
        "next_gate": "freeze_public_branch_capture_protocol" if passed else "stop_native_replay_adapter",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-project-revision", required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/proper_v2_3/tau3_branch_replay_native_smoke/result.json")
    args = parser.parse_args()
    result = run(args.expected_project_revision)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes((json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    try:
        import jsonschema
    except ImportError:
        pass
    else:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(result)
    print(json.dumps({"output": str(args.output), "passed": result["passed"], "native_execution_count": result["native_execution_count"], "model_loaded": False, "gpu_used": False}, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
