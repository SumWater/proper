"""CPU-only native-tool branch screen for the frozen PROPER v2.3 design.

Task/evaluator fields are read only by the offline qualification audit.  Native
tool fixtures are derived independently from fresh copies of the public tau DB;
the controller receives only action, effect, evidence, and ledger contracts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import types
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Mapping

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from failure_memory.proper_v2 import DecisionPhase, RecoveryOperation, RetrySafety
from failure_memory.proper_v2.v2_2 import EvidenceStatus, TriggerStatus
from failure_memory.proper_v2.v2_3 import (
    ActionEffectClass,
    ActionEffectContract,
    ActionExecutionLedger,
    ActionPurpose,
    ActionSpec,
    BudgetPolicy,
    ControllerDisposition,
    EvidenceRecord,
    EvidenceSource,
    ExecutionStatus,
    initial_controller_state,
    observe_execution,
    resolve_verification,
    review_action_proposal,
)

DEFAULT_CONFIG = ROOT / "configs" / "proper_v2_3" / "tau3_branch_screen_v2_3.yaml"
DEFAULT_OUTPUT = ROOT / "outputs" / "proper_v2_3" / "tau3_branch_screen" / "branch_screen.json"
DEPENDENCY_ENV = "PROPER_V2_3_TAU3_DEPENDENCY_DIR"


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def git(source: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(source), *args], check=True, capture_output=True,
        text=True, encoding="utf-8"
    ).stdout.strip()


def execution_manifest(source: Path) -> dict[str, Any]:
    files: list[Path] = []
    for relative in (
        "src/tau2/domains/airline", "src/tau2/domains/retail",
        "src/tau2/environment", "src/tau2/utils",
    ):
        files.extend(sorted((source / relative).glob("*.py")))
    for domain in ("airline", "retail"):
        base = source / "data" / "tau2" / "domains" / domain
        files.extend(base / name for name in ("db.json", "tasks.json", "split_tasks.json", "policy.md"))
    records = [
        {"path": path.relative_to(source).as_posix(), "sha256": sha256(path), "bytes": path.stat().st_size}
        for path in sorted(files)
    ]
    return {
        "file_count": len(records),
        "bytes": sum(item["bytes"] for item in records),
        "sha256": canonical_sha256(records),
    }


def audit_frozen_inputs(config: Mapping[str, Any]) -> dict[str, Any]:
    checks = []
    for name, item in config["frozen_project_inputs"].items():
        path = ROOT / item["path"]
        actual = sha256(path)
        checks.append({"name": name, "path": item["path"], "sha256": actual, "passed": actual == item["sha256"]})
    memory = load_object(ROOT / config["frozen_project_inputs"]["proper_v1_memory_bank"]["path"])
    actual_v1 = sorted({str(item["provenance"]) for item in memory["memory_sources"]})
    v2 = load_object(ROOT / config["frozen_project_inputs"]["proper_v2_exposed_manifest"]["path"])
    actual_v2 = sorted({str(item["semantic_family"]) for item in v2["records"]})
    expected = config["exclusion_audit"]
    new = set(expected["new_failure_families"])
    return {
        "frozen_hash_checks": checks,
        "proper_v1_failure_provenance": actual_v1,
        "proper_v2_exposed_semantic_families": actual_v2,
        "proper_v1_exact_match": actual_v1 == expected["proper_v1_failure_provenance"],
        "proper_v2_exact_match": actual_v2 == expected["proper_v2_exposed_semantic_families"],
        "new_family_string_disjoint_from_v1_and_v2": not new.intersection(actual_v1 + actual_v2),
        "candidate_targets_used_to_tune_controller": expected["candidate_targets_used_to_tune_controller"],
    }


def audit_candidates(source: Path, config: Mapping[str, Any]) -> list[dict[str, Any]]:
    by_domain: dict[str, tuple[dict[str, Any], set[str]]] = {}
    for domain in {str(item["domain"]) for item in config["candidates"]}:
        base = source / "data" / "tau2" / "domains" / domain
        tasks = json.loads((base / "tasks.json").read_text(encoding="utf-8"))
        split = load_object(base / "split_tasks.json")
        by_domain[domain] = ({str(task["id"]): task for task in tasks}, {str(value) for value in split["train"]})
    records = []
    for item in config["candidates"]:
        tasks, train = by_domain[item["domain"]]
        task = tasks[item["source_task_id"]]
        actions = task["evaluation_criteria"]["actions"]
        action = actions[item["action_index"]]
        after = len(actions) - item["action_index"] - 1
        records.append({
            "pair_id": item["pair_id"], "domain": item["domain"],
            "source_task_id_sha256": canonical_sha256(item["source_task_id"]),
            "source_split": "train" if item["source_task_id"] in train else "not_train",
            "action_index": item["action_index"], "guarded_action_name": action["name"],
            "action_proxy_sha256": canonical_sha256(action), "actions_after": after,
            "name_matches": action["name"] == item["guarded_action_name"],
            "depth_passed": after >= item["minimum_actions_after"],
        })
    return records


def install_tau_import_shim(source: Path, dependency_dir: Path | None) -> None:
    if dependency_dir is not None:
        if not dependency_dir.is_dir():
            raise RuntimeError(f"tau dependency directory does not exist: {dependency_dir}")
        sys.path.insert(0, str(dependency_dir))
    package = types.ModuleType("tau2")
    package.__path__ = [str(source / "src" / "tau2")]
    package.__package__ = "tau2"
    sys.modules["tau2"] = package


def native_toolkit(source: Path, domain: str) -> Any:
    db_path = source / "data" / "tau2" / "domains" / domain / "db.json"
    if domain == "airline":
        from tau2.domains.airline.data_model import FlightDB
        from tau2.domains.airline.tools import AirlineTools
        return AirlineTools(FlightDB.load(db_path))
    from tau2.domains.retail.data_model import RetailDB
    from tau2.domains.retail.tools import RetailTools
    return RetailTools(RetailDB.load(db_path))


def address(pair_id: str) -> dict[str, str]:
    suffix = int(pair_id.rsplit("-", 1)[1])
    return {"address1": f"{100 + suffix} Observable Ave", "address2": "",
            "city": "San Francisco", "state": "CA", "country": "USA", "zip": f"94{suffix:03d}"}


def nth(values: list[Any], ordinal: int) -> Any:
    if not values:
        raise RuntimeError("fixture pool is empty")
    return values[ordinal % len(values)]


def fixture(candidate: Mapping[str, Any], tools: Any) -> dict[str, Any]:
    strategy = candidate["fixture_strategy"]
    ordinal = int(candidate["fixture_ordinal"])
    db = tools.db
    if strategy == "airline_reservation_read":
        rid = nth(sorted(db.reservations), ordinal)
        return {"action": ActionSpec("get_reservation_details", {"reservation_id": rid})}
    if strategy in {"retail_user_name_zip_read", "retail_user_email_read"}:
        uid = nth(sorted(db.users), ordinal); user = db.users[uid]
        args = ({"first_name": user.name.first_name, "last_name": user.name.last_name, "zip": user.address.zip}
                if strategy.endswith("name_zip_read") else {"email": user.email})
        return {"action": ActionSpec(candidate["guarded_action_name"], args)}
    if strategy == "retail_user_address_setting":
        uid = nth(sorted(db.users), ordinal); args = {"user_id": uid, **address(candidate["pair_id"])}
        stale = {**args, "user_id": f"stale-{uid}"}
        return {"action": ActionSpec("modify_user_address", args), "stale": ActionSpec("modify_user_address", stale),
                "verifier": ActionSpec("get_user_details", {"user_id": uid}), "expected_address": address(candidate["pair_id"])}
    if strategy == "retail_pending_address_setting":
        orders = sorted(oid for oid, order in db.orders.items() if order.status == "pending")
        oid = nth(orders, ordinal); args = {"order_id": oid, **address(candidate["pair_id"])}
        stale = {**args, "order_id": f"#STALE{ordinal:04d}"}
        return {"action": ActionSpec("modify_pending_order_address", args), "stale": ActionSpec("modify_pending_order_address", stale),
                "verifier": ActionSpec("get_order_details", {"order_id": oid}), "expected_address": address(candidate["pair_id"])}
    if strategy == "airline_cancel_unknown":
        reservations = sorted(rid for rid, value in db.reservations.items() if value.status != "cancelled")
        rid = nth(reservations, ordinal)
        return {"action": ActionSpec("cancel_reservation", {"reservation_id": rid}),
                "verifier": ActionSpec("get_reservation_details", {"reservation_id": rid}), "expected_status": "cancelled"}
    if strategy == "retail_cancel_unknown":
        orders = sorted(oid for oid, order in db.orders.items() if order.status == "pending")
        oid = nth(orders, ordinal)
        return {"action": ActionSpec("cancel_pending_order", {"order_id": oid, "reason": "no longer needed"}),
                "verifier": ActionSpec("get_order_details", {"order_id": oid}), "expected_status": "cancelled"}
    if strategy in {"retail_return_unknown", "retail_exchange_unknown"}:
        orders = [db.orders[oid] for oid in sorted(db.orders) if db.orders[oid].status == "delivered"]
        if strategy == "retail_return_unknown":
            order = nth(orders, ordinal); item = order.items[0]
            args = {"order_id": order.order_id, "item_ids": [item.item_id],
                    "payment_method_id": order.payment_history[0].payment_method_id}
            return {"action": ActionSpec("return_delivered_order_items", args),
                    "verifier": ActionSpec("get_order_details", {"order_id": order.order_id}), "expected_status": "return requested"}
        viable = []
        for order in orders:
            for old in order.items:
                variants = db.products[old.product_id].variants
                alternatives = sorted(
                    v.item_id for v in variants.values()
                    if v.available and v.item_id != old.item_id and v.price <= old.price
                )
                if alternatives:
                    methods = db.users[order.user_id].payment_methods
                    credit = sorted(key for key in methods if key.startswith("credit_card"))
                    viable.append((order, old, alternatives[0], credit[0] if credit else order.payment_history[0].payment_method_id))
                    break
        order, old, new_id, payment = nth(viable, ordinal)
        args = {"order_id": order.order_id, "item_ids": [old.item_id], "new_item_ids": [new_id], "payment_method_id": payment}
        return {"action": ActionSpec("exchange_delivered_order_items", args),
                "verifier": ActionSpec("get_order_details", {"order_id": order.order_id}), "expected_status": "exchange requested"}
    raise ValueError(f"unknown fixture strategy: {strategy}")


def contract(effect: str) -> ActionEffectContract:
    classification = (f"public_tool_implementation:{effect}",)
    if effect == "read_only":
        return ActionEffectContract(ActionEffectClass.READ_ONLY, classification, RetrySafety.SAFE,
                                    ("public_contract:no_state_mutation",))
    if effect == "idempotent_state_setting":
        return ActionEffectContract(ActionEffectClass.IDEMPOTENT_STATE_SETTING, classification, RetrySafety.SAFE,
                                    ("public_contract:absolute_state_assignment",), True,
                                    ("public_contract:read_back_supported",))
    return ActionEffectContract(ActionEffectClass.NON_IDEMPOTENT_SIDE_EFFECT, classification, RetrySafety.UNSAFE,
                                ("public_contract:repeat_can_duplicate_or_conflict",), True,
                                ("public_contract:status_read_supported",))


READ_CONTRACT = ActionEffectContract(ActionEffectClass.READ_ONLY, ("public_tool_implementation:read_only",),
                                     RetrySafety.SAFE, ("public_contract:no_state_mutation",))


def evidence(code: str, step: int, source: EvidenceSource = EvidenceSource.TOOL_RESULT) -> tuple[EvidenceRecord, ...]:
    return (EvidenceRecord(source, code, step),)


def execute(tools: Any, action: ActionSpec) -> Any:
    return getattr(tools, action.tool_name)(**dict(action.arguments))


def record(ledger: ActionExecutionLedger, entry_id: str, status: ExecutionStatus, code: str, step: int) -> ActionExecutionLedger:
    ledger = ledger.mark_executed(entry_id, evidence=evidence("dispatch_started", step, EvidenceSource.CONTROLLER))
    return ledger.record_outcome(entry_id, status=status, evidence=evidence(code, step))


def verify_native(result: Any, fx: Mapping[str, Any]) -> bool:
    if "expected_status" in fx:
        return result.status == fx["expected_status"]
    expected = fx["expected_address"]
    return all(getattr(result.address, key) == value for key, value in expected.items())


def run_pair(candidate: Mapping[str, Any], tools: Any, budget: BudgetPolicy) -> dict[str, Any]:
    fx = fixture(candidate, tools); action = fx["action"]; effect = candidate["effect_class"]
    phase = DecisionPhase(candidate["phase"])
    operation = (RecoveryOperation.INVOKE_PREREQUISITE if effect == "read_only" else
                 RecoveryOperation.REPAIR_ARGUMENTS if effect == "idempotent_state_setting" else RecoveryOperation.RETRY_SAME_ACTION)
    state = initial_controller_state(phase=phase, selected_memory_experience_id=f"memory::{candidate['failure_family']}",
                                     memory_operation=operation, memory_action=action, budget_policy=budget)
    ledger = ActionExecutionLedger(candidate["pair_id"]); native_calls = Counter(); step = 0
    if "stale" in fx:
        stale = fx["stale"]
        ledger, prefix = ledger.append_proposal(action=stale, effect_contract=contract(effect), phase=phase,
            purpose=ActionPurpose.ORDINARY_TASK, disposition=ControllerDisposition.ALLOW,
            decision_allowed=True, reason_codes=("observable_failed_prefix",))
        step += 1; native_calls[stale.tool_name] += 1
        try:
            execute(tools, stale)
            raise AssertionError("stale reference unexpectedly succeeded")
        except ValueError:
            ledger = record(ledger, prefix.entry_id, ExecutionStatus.FAILED, "public_tool_error:reference_not_found", step)
    ledger, decision = review_action_proposal(state=state, ledger=ledger, action=action,
        effect_contract=contract(effect), purpose=ActionPurpose.RECOVERY)
    if not decision.decision_allowed or decision.ledger_entry_id is None:
        raise AssertionError(f"recovery was blocked: {decision.reason_code}")
    state = decision.state; recovery_id = decision.ledger_entry_id; step += 1
    result = execute(tools, action); native_calls[action.tool_name] += 1
    if effect == "non_idempotent_side_effect":
        ledger = record(ledger, recovery_id, ExecutionStatus.OUTCOME_UNKNOWN, "transport:response_suppressed_after_dispatch", step)
        state = observe_execution(state=state, ledger=ledger, entry_id=recovery_id)
    else:
        ledger = record(ledger, recovery_id, ExecutionStatus.SUCCEEDED, "public_tool_result:success", step)
        state = observe_execution(state=state, ledger=ledger, entry_id=recovery_id,
            trigger_status=TriggerStatus.CLEARED if effect == "read_only" else TriggerStatus.UNKNOWN,
            success_evidence_status=EvidenceStatus.SATISFIED if effect == "read_only" else EvidenceStatus.UNKNOWN)
    verification_passed = True
    if "verifier" in fx:
        verifier = fx["verifier"]
        ledger, decision = review_action_proposal(state=state, ledger=ledger, action=verifier,
            effect_contract=READ_CONTRACT, purpose=ActionPurpose.VERIFICATION, verifies_entry_id=recovery_id)
        if not decision.decision_allowed or decision.ledger_entry_id is None:
            raise AssertionError(f"verification was blocked: {decision.reason_code}")
        state = decision.state; step += 1; native_calls[verifier.tool_name] += 1
        verification_result = execute(tools, verifier); verification_passed = verify_native(verification_result, fx)
        if not verification_passed:
            raise AssertionError("native read-back did not establish success")
        ledger = record(ledger, decision.ledger_entry_id, ExecutionStatus.SUCCEEDED, "public_state:read_back_satisfied", step)
        if effect == "non_idempotent_side_effect":
            ledger = ledger.record_outcome(recovery_id, status=ExecutionStatus.SUCCEEDED,
                                           evidence=evidence("public_state:unknown_outcome_resolved", step, EvidenceSource.PUBLIC_STATE))
        state = resolve_verification(state=state, ledger=ledger, verified_entry_id=recovery_id,
            verified_status=ExecutionStatus.SUCCEEDED, trigger_status=TriggerStatus.CLEARED,
            success_evidence_status=EvidenceStatus.SATISFIED)
    continuation_allowed = 0
    for index in range(2):
        ordinary = ActionSpec("scripted_public_continuation_read", {"pair": candidate["pair_id"], "step": index})
        ledger, decision = review_action_proposal(state=state, ledger=ledger, action=ordinary,
            effect_contract=READ_CONTRACT, purpose=ActionPurpose.ORDINARY_TASK)
        if not decision.decision_allowed or decision.ledger_entry_id is None:
            raise AssertionError(f"ordinary continuation blocked: {decision.reason_code}")
        step += 1; ledger = record(ledger, decision.ledger_entry_id, ExecutionStatus.SUCCEEDED,
                                   "scripted_public_result:continuation_observed", step)
        state = observe_execution(state=decision.state, ledger=ledger, entry_id=decision.ledger_entry_id)
        continuation_allowed += 1
    ledger, repeat = review_action_proposal(state=state, ledger=ledger, action=action,
        effect_contract=contract(effect), purpose=ActionPurpose.ORDINARY_TASK)
    repeat_blocked = not repeat.decision_allowed and repeat.disposition in {ControllerDisposition.REPLAN, ControllerDisposition.STOP}
    return {
        "pair_id": candidate["pair_id"], "domain": candidate["domain"], "phase": candidate["phase"],
        "failure_family": candidate["failure_family"], "effect_class": effect,
        "fixture_strategy": candidate["fixture_strategy"], "native_tool_calls": dict(sorted(native_calls.items())),
        "guarded_native_execution_count": native_calls[action.tool_name], "verification_passed": verification_passed,
        "lifecycle_after_recovery": state.lifecycle_status.value, "planning_mode_after_recovery": state.planning_mode.value,
        "continuation_actions_allowed": continuation_allowed, "exact_repeat_blocked": repeat_blocked,
        "repeat_disposition": repeat.disposition.value, "repeat_reason": repeat.reason_code,
        "final_budgets": repeat.state.budgets.to_mapping(), "ledger": ledger.to_mapping(),
    }


def run(config_path: Path, output_path: Path, dependency_dir: Path | None) -> dict[str, Any]:
    config = load_object(config_path); source = ROOT / config["source_lock"]["local_directory"]
    source_lock = config["source_lock"]; manifest = execution_manifest(source)
    source_checks = {
        "revision": git(source, "rev-parse", "HEAD"),
        "tag_object": git(source, "rev-parse", f"{source_lock['tag']}^{{tag}}"),
        "tag_commit": git(source, "rev-parse", f"{source_lock['tag']}^{{commit}}"),
        "execution_manifest": manifest,
        "database_sha256": {domain: sha256(source / "data" / "tau2" / "domains" / domain / "db.json") for domain in ("airline", "retail")},
    }
    exclusion = audit_frozen_inputs(config); candidates = audit_candidates(source, config)
    install_tau_import_shim(source, dependency_dir)
    budget = BudgetPolicy(**config["budget_policy"])
    pairs = [run_pair(item, native_toolkit(source, item["domain"]), budget) for item in config["candidates"]]
    effects = Counter(item["effect_class"] for item in pairs); domains = {item["domain"] for item in pairs}
    gates = config["gates"]
    checks = {
        "source_revision_pinned": source_checks["revision"] == source_lock["revision"] == source_checks["tag_commit"],
        "tag_object_pinned": source_checks["tag_object"] == source_lock["tag_object"],
        "execution_manifest_pinned": manifest == {"file_count": source_lock["execution_manifest_file_count"], "bytes": source_lock["execution_manifest_bytes"], "sha256": source_lock["execution_manifest_sha256"]},
        "database_hashes_pinned": source_checks["database_sha256"] == source_lock["database_sha256"],
        "frozen_inputs_pinned": all(item["passed"] for item in exclusion["frozen_hash_checks"]),
        "exclusion_audit_passed": exclusion["proper_v1_exact_match"] and exclusion["proper_v2_exact_match"] and exclusion["new_family_string_disjoint_from_v1_and_v2"] and not exclusion["candidate_targets_used_to_tune_controller"],
        "candidate_membership_passed": all(item["source_split"] == "train" and item["name_matches"] and item["depth_passed"] for item in candidates),
        "candidate_count_passed": len(pairs) == gates["required_candidate_count"],
        "domain_count_passed": len(domains) >= gates["required_domains"],
        "effect_balance_passed": all(effects[name] >= gates["required_per_effect_class"] for name in ("read_only", "idempotent_state_setting", "non_idempotent_side_effect")),
        "lifecycle_and_continuation_passed": all(item["lifecycle_after_recovery"] == "consumed" and item["planning_mode_after_recovery"] == "ordinary_task_planning" and item["continuation_actions_allowed"] >= gates["required_continuation_actions"] for item in pairs),
        "repeat_safety_passed": all(item["exact_repeat_blocked"] for item in pairs),
        "non_idempotent_single_execution_passed": all(item["guarded_native_execution_count"] == gates["require_non_idempotent_native_execution_count"] for item in pairs if item["effect_class"] == "non_idempotent_side_effect"),
    }
    passed = all(checks.values())
    result = {
        "schema_version": 1, "run_kind": "proper_v2_3_cpu_scripted_development_branch_screen",
        "config_sha256": sha256(config_path), "passed": passed, "checks": checks,
        "source_checks": source_checks, "exclusion_audit": exclusion, "candidate_audit": candidates,
        "summary": {"qualified_development_pair_count": len(pairs) if passed else 0,
                    "effect_counts": dict(sorted(effects.items())), "domain_count": len(domains),
                    "new_development_target_capacity_available": passed,
                    "new_heldout_target_capacity": 0, "development_model_run_authorized": False,
                    "confirmatory_claim_authorized": False},
        "pairs": pairs,
        "boundary": {**config["boundary"], "method_input_fields": ["action_spec", "action_effect_contract", "observable_evidence", "action_execution_ledger"],
                     "model_loaded": False, "gpu_used": False, "target_tasks_executed": False},
        "next_gate": "freeze_five_condition_development_protocol_before_any_model_run" if passed else "stop_and_preserve_negative_branch_screen",
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dependency-dir", type=Path, default=None)
    args = parser.parse_args()
    dependency = args.dependency_dir
    if dependency is None and os.environ.get(DEPENDENCY_ENV):
        dependency = Path(os.environ[DEPENDENCY_ENV])
    result = run(args.config.resolve(), args.output.resolve(), dependency.resolve() if dependency else None)
    print(json.dumps({"passed": result["passed"], "summary": result["summary"], "next_gate": result["next_gate"]}, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
