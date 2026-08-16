"""Audit the current E6 external held-out capacity without a model or task play."""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import yaml


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "configs" / "paper_2026" / "e6_capacity_gate_v1_0.yaml"


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def root_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify_inputs(config: Mapping[str, Any]) -> dict[str, str]:
    verified = {}
    for name, item in config["inputs"].items():
        path = root_path(item["path"])
        observed = sha256_file(path)
        if observed != str(item["sha256"]):
            raise RuntimeError(f"input hash mismatch for {name}: {observed}")
        verified[name] = observed
    return verified


def audit(config: Mapping[str, Any], verified: Mapping[str, str]) -> tuple[dict[str, Any], dict[str, Any], str]:
    first_stage = read_json(root_path(config["inputs"]["first_stage_validation"]["path"]))
    tau_source = read_json(root_path(config["inputs"]["tau3_source_qualification"]["path"]))
    tau_branch = read_json(root_path(config["inputs"]["tau3_local_branch_validation"]["path"]))
    policy = config["source_policy"]
    minimum = int(config["capacity_requirement"]["minimum_qualified_independent_heldout_tasks"])
    minimum_families = int(config["capacity_requirement"]["minimum_failure_or_recovery_families"])

    if first_stage["target_capacity_design"]["new_target_capacity_available"]:
        raise RuntimeError("frozen ToolSandbox capacity unexpectedly changed")
    if int(first_stage["target_capacity_design"]["candidate_source_count"]) != 0:
        raise RuntimeError("frozen ToolSandbox candidate source count unexpectedly changed")
    source_result = tau_source["source_qualification"]
    prospective = int(source_result["prospective_partition"]["heldout_task_count"])
    if prospective != int(policy["tau3"]["prospective_heldout_tasks"]):
        raise RuntimeError("Tau3 prospective held-out count differs from capacity policy")
    branch_boundary = tau_branch["boundary"]
    if int(branch_boundary["qualified_development_pair_count"]) != int(
        policy["tau3"]["local_development_pairs"]
    ):
        raise RuntimeError("Tau3 local development-pair count differs from capacity policy")
    if int(branch_boundary["new_heldout_target_capacity"]) != 0:
        raise RuntimeError("local implementation self-test cannot create held-out capacity")

    remote_pattern = str(root_path(policy["tau3"]["remote_validation_glob"]))
    remote_validations = sorted(Path(path) for path in glob.glob(remote_pattern))
    qualified = int(policy["tau3"]["currently_qualified_heldout_tasks"])
    family_count = 0
    gate_passed = qualified >= minimum and family_count >= minimum_families
    if gate_passed:
        raise RuntimeError("current frozen audit must not authorize an unqualified E6 model run")

    result = {
        "schema_version": 1,
        "stage_id": "e6_external_capacity_gate",
        "status": "capacity_not_yet_qualified_no_model_run_authorized",
        "input_identities": dict(verified),
        "requirements": {
            "minimum_qualified_independent_heldout_tasks": minimum,
            "minimum_failure_or_recovery_families": minimum_families,
        },
        "sources": {
            "toolsandbox": {
                "eligible_candidates": int(policy["toolsandbox"]["current_eligible_candidates"]),
                "exhausted": bool(policy["toolsandbox"]["exhausted"]),
                "qualified_for_e6": False,
            },
            "toolmisusebench": {
                "qualified_for_e6": False,
                "exclusion_reason": policy["toolmisusebench"]["exclusion_reason"],
            },
            "tau3": {
                "prospective_heldout_tasks": prospective,
                "qualified_heldout_tasks": qualified,
                "qualified_failure_or_recovery_families": family_count,
                "local_development_pairs": int(branch_boundary["qualified_development_pair_count"]),
                "formal_remote_branch_validation_count": len(remote_validations),
                "formal_remote_branch_validation_paths": [
                    str(path.relative_to(ROOT)).replace("\\", "/") for path in remote_validations
                ],
                "source_interpretation": source_result["interpretation"],
            },
        },
        "decision": {
            "current_capacity_gate_passed": gate_passed,
            "e6_model_or_gpu_run_authorized": False,
            "continue_cpu_only_tau3_qualification": bool(
                config["decision"]["continue_cpu_only_qualification"]
            ),
            "qualification_stop_review_date": str(
                config["decision"]["qualification_stop_review_date"]
            ),
            "next_required_gate": "formal_remote_tau3_development_branch_validation",
            "next_required_heldout_stage": "prospective_tau3_heldout_pair_qualification",
            "remote_branch_pass_alone_will_not_create_heldout_capacity": True,
        },
        "boundary": {
            "model_loaded": False,
            "model_outputs_read": False,
            "gpu_used": False,
            "target_tasks_played": False,
            "local_development_pairs_relabelled_as_heldout": False,
            "prospective_tasks_relabelled_as_qualified": False,
        },
    }
    audit_payload = {
        "schema_version": 1,
        "stage_id": "e6_external_capacity_gate_audit",
        "checks": {
            "all_input_hashes_match": True,
            "toolsandbox_zero_capacity_preserved": True,
            "toolmisusebench_not_reused_as_external": True,
            "tau3_prospective_is_not_treated_as_qualified": True,
            "tau3_local_development_is_not_treated_as_remote_or_heldout": True,
            "no_model_or_gpu_authority_created": True,
        },
        "remote_validation_files_observed": len(remote_validations),
    }
    report = (
        "# E6 current external-capacity decision\n\n"
        f"- Required qualified held-out tasks: {minimum}; currently qualified: {qualified}.\n"
        f"- Required failure/recovery families: {minimum_families}; currently qualified: {family_count}.\n"
        "- ToolSandbox remains exhausted and ToolMisuseBench is not an independent external source.\n"
        f"- Tau3 reserves {prospective} prospective held-out tasks, but none is yet a qualified pair.\n"
        f"- Formal remote Tau3 branch validations observed: {len(remote_validations)}.\n"
        "- Decision: do not run E6 models or GPUs. Continue only CPU qualification until the "
        f"{config['decision']['qualification_stop_review_date']} review date.\n"
        "- A passing remote development branch screen is necessary but not sufficient; a separate "
        "prospective held-out pair qualification stage must still establish at least 30 tasks across "
        "at least three failure or recovery families.\n"
    )
    return result, audit_payload, report


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit current E6 external capacity without a model.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    config_path = root_path(args.config)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    verified = verify_inputs(config)
    result, audit_payload, report = audit(config, verified)
    output_root = root_path(config["outputs"]["root"])
    write_json(output_root / config["outputs"]["result"], result)
    write_json(output_root / config["outputs"]["audit"], audit_payload)
    report_path = output_root / config["outputs"]["report"]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(canonical({"status": result["status"], **result["decision"]}))


if __name__ == "__main__":
    main()
