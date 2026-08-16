"""Freeze the imported Tau3 remote CPU gate result and its paper claim boundary."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import yaml


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "configs" / "paper_2026" / "e6_remote_cpu_gate_20260812.yaml"


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def root_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify_inputs(config: Mapping[str, Any]) -> dict[str, str]:
    verified: dict[str, str] = {}
    for name, item in config["inputs"].items():
        path = root_path(item["path"])
        observed = sha256_file(path)
        if observed != str(item["sha256"]):
            raise RuntimeError(f"input hash mismatch for {name}: {observed}")
        verified[name] = observed
    return verified


def require_equal(label: str, observed: Any, expected: Any) -> None:
    if observed != expected:
        raise RuntimeError(f"{label} mismatch: observed={observed!r}, expected={expected!r}")


def build_record(config: Mapping[str, Any], verified: Mapping[str, str]) -> tuple[dict[str, Any], dict[str, Any], str]:
    remote = read_json(root_path(config["inputs"]["remote_validation"]["path"]))
    branch = read_json(root_path(config["inputs"]["branch_screen"]["path"]))
    identity = config["expected_remote_identity"]
    scientific = config["expected_scientific_result"]
    envelope = config["expected_envelope_result"]
    disposition = config["paper_disposition"]

    require_equal("run_id", remote["run_id"], identity["run_id"])
    require_equal("project_revision", remote["preconditions"]["project_revision"], identity["project_revision"])
    require_equal("tau_revision", remote["preconditions"]["tau_revision"], identity["tau_revision"])
    require_equal("source_manifest", remote["source_manifest"]["manifest_sha256"], identity["source_manifest_sha256"])
    require_equal("tracked_worktree_clean", remote["preconditions"]["tracked_worktree_clean"], True)
    require_equal("required_ancestor_present", remote["preconditions"]["required_ancestor_present"], True)
    require_equal("cpu_guard", remote["preconditions"]["cuda_visible_devices"], "-1")

    summary = branch["summary"]
    require_equal("branch_screen_passed", branch["passed"], scientific["branch_screen_passed"])
    require_equal("qualified_development_pairs", summary["qualified_development_pair_count"], scientific["qualified_development_pairs"])
    require_equal("effect_counts", summary["effect_counts"], scientific["effect_counts"])
    require_equal("domain_count", summary["domain_count"], scientific["domain_count"])
    require_equal("qualified_heldout_pairs", summary["new_heldout_target_capacity"], scientific["qualified_heldout_pairs"])
    require_equal("development_model_run_authorized", summary["development_model_run_authorized"], scientific["development_model_run_authorized"])
    require_equal("confirmatory_claim_authorized", summary["confirmatory_claim_authorized"], scientific["confirmatory_claim_authorized"])

    tests = remote["repository_tests"]
    require_equal("envelope_passed", remote["passed"], envelope["envelope_passed"])
    require_equal("schema_passed", remote["schema_validation"]["passed"], envelope["schema_passed"])
    require_equal("execution_error_present", remote["execution_error"] is not None, envelope["execution_error_present"])
    require_equal("repository_tests_run", tests["tests_run"], envelope["repository_tests_run"])
    require_equal("repository_test_failures", tests["failure_count"], envelope["repository_test_failures"])
    require_equal("repository_test_errors", tests["error_count"], envelope["repository_test_errors"])
    require_equal("repository_test_skips", tests["skipped_count"], envelope["repository_test_skips"])
    runner_output = str(tests["runner_output"])
    cryptography_occurrences = runner_output.count("ModuleNotFoundError: No module named 'cryptography'")
    lazy_occurrences = runner_output.count("AssertionError: True is not false")
    require_equal("missing_cryptography_occurrences", cryptography_occurrences, envelope["missing_cryptography_occurrences"])
    require_equal("lazy_import_state_pollution_occurrences", lazy_occurrences, envelope["lazy_import_state_pollution_occurrences"])

    infrastructure_only_envelope_failure = bool(
        branch["passed"]
        and remote["schema_validation"]["passed"]
        and remote["execution_error"] is None
        and tests["failure_count"] == 1
        and tests["error_count"] == 8
        and cryptography_occurrences == 8
        and lazy_occurrences == 1
    )
    record = {
        "schema_version": 1,
        "stage_id": "e6_remote_cpu_gate_record",
        "status": "recorded_current_paper_e6_stopped",
        "input_identities": dict(verified),
        "remote_identity": {
            "run_id": remote["run_id"],
            "project_revision": remote["preconditions"]["project_revision"],
            "tau_revision": remote["preconditions"]["tau_revision"],
            "source_manifest_sha256": remote["source_manifest"]["manifest_sha256"],
            "tracked_worktree_clean": True,
            "required_ancestor_present": True,
            "cpu_only": True,
        },
        "scientific_result": {
            "development_branch_screen_passed": bool(branch["passed"]),
            "qualified_development_pairs": summary["qualified_development_pair_count"],
            "effect_counts": summary["effect_counts"],
            "domain_count": summary["domain_count"],
            "qualified_heldout_pairs": summary["new_heldout_target_capacity"],
            "development_model_run_authorized": summary["development_model_run_authorized"],
            "confirmatory_claim_authorized": summary["confirmatory_claim_authorized"],
        },
        "envelope_result": {
            "passed": bool(remote["passed"]),
            "schema_passed": bool(remote["schema_validation"]["passed"]),
            "execution_error_present": remote["execution_error"] is not None,
            "repository_tests": {
                "tests_run": tests["tests_run"],
                "failure_count": tests["failure_count"],
                "error_count": tests["error_count"],
                "skipped_count": tests["skipped_count"],
            },
            "known_infrastructure_findings": {
                "missing_cryptography_errors": cryptography_occurrences,
                "in_process_lazy_import_state_pollution_failures": lazy_occurrences,
            },
            "infrastructure_only_failure_classification": infrastructure_only_envelope_failure,
            "negative_envelope_preserved": bool(disposition["preserve_negative_envelope"]),
        },
        "paper_claim_boundary": {
            "current_paper_e6_status": disposition["current_paper_e6_status"],
            "stop_reason": disposition["stop_reason"],
            "may_support_efficacy_claim": bool(disposition["use_as_primary_or_secondary_efficacy_evidence"]),
            "may_support_reproducibility_or_limitation_statement": bool(disposition["use_as_reproducibility_and_limitation_evidence"]),
            "future_e6_work_is_separate": bool(disposition["future_e6_work_must_use_separate_branch"]),
            "p0_to_e5_remain_frozen": bool(disposition["frozen_p0_to_e5_must_not_change"]),
        },
    }
    audit = {
        "schema_version": 1,
        "stage_id": "e6_remote_cpu_gate_record_audit",
        "checks": {
            "input_hashes_match": True,
            "remote_project_and_tau_identities_match": True,
            "remote_preconditions_passed": True,
            "development_screen_and_envelope_are_reported_separately": True,
            "zero_heldout_capacity_is_preserved": True,
            "negative_envelope_is_not_relabelled_as_passed": True,
            "no_efficacy_claim_is_authorized": True,
        },
    }
    report = (
        "# E6 Tau3 remote CPU gate: paper evidence boundary\n\n"
        "## Recorded outcome\n\n"
        "The CPU scripted development branch screen itself passed 12/12 qualified development pairs "
        "across two domains, with four read-only, four idempotent state-setting, and four "
        "non-idempotent side-effect pairs. The schema and all remote identity/precondition checks passed.\n\n"
        "The enclosing remote validation did not pass. Its repository suite ran 284 tests and reported "
        "one failure and eight errors. All eight errors were missing-`cryptography` dependency errors; "
        "the single failure was an in-process lazy-import assertion after Tau3 had already been loaded "
        "by the branch screen. The original negative envelope is preserved and is not relabelled.\n\n"
        "## Paper boundary\n\n"
        "This result establishes development-only scripted capacity. It establishes zero qualified "
        "held-out pairs, authorizes no development model run, and authorizes no confirmatory or efficacy "
        "claim. The current paper records E6 as stopped for insufficient qualified held-out capacity. "
        "It may be cited only as a reproducibility/limitation record or future-work motivation.\n\n"
        "Any infrastructure repair, held-out qualification, or model execution belongs on a separate "
        "E6 branch and must not alter the frozen P0--E5 artifacts or claims.\n"
    )
    return record, audit, report


def main() -> None:
    parser = argparse.ArgumentParser(description="Record imported E6 remote CPU gate evidence.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    config_path = root_path(args.config)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    verified = verify_inputs(config)
    record, audit, report = build_record(config, verified)
    output_root = root_path(config["outputs"]["root"])
    write_json(output_root / config["outputs"]["record"], record)
    write_json(output_root / config["outputs"]["audit"], audit)
    report_path = output_root / config["outputs"]["report"]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(canonical({"status": record["status"], **record["paper_claim_boundary"]}))


if __name__ == "__main__":
    main()
