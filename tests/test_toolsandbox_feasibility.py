from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "proper_v2"))

from toolsandbox_feasibility import (  # noqa: E402
    load_config,
    run_audit,
    scenario_extensions,
    summarize,
)
from toolsandbox_dynamic_pilot import (  # noqa: E402
    load_config as load_dynamic_config,
    python_source_manifest,
    semantic_family,
)
from toolsandbox_scripted_smoke import (  # noqa: E402
    load_config as load_scripted_smoke_config,
)
from toolsandbox_selector_capacity import (  # noqa: E402
    configured_legacy_memories,
    load_config as load_selector_capacity_config,
    resolve_and_verify_input,
    summarize as summarize_selector_capacity,
)
from toolsandbox_action_memory_preparation import (  # noqa: E402
    behavior_signature,
    load_config as load_action_memory_config,
    resolve_and_verify as resolve_action_memory_input,
)
from toolsandbox_selector_capacity_v2 import (  # noqa: E402
    full_behavior_signature,
    intervention_signature,
    load_config as load_behavioral_capacity_config,
    summarize as summarize_behavioral_capacity,
)
from toolsandbox_selector_capacity_v2_1 import (  # noqa: E402
    load_config as load_phase_aware_capacity_config,
    phase_aware_target,
    resolve_and_verify as resolve_phase_aware_source,
)
from failure_memory.proper_v2 import (  # noqa: E402
    ContinuationPolicy,
    RecoveryOperation,
)


class ToolSandboxFeasibilityTests(unittest.TestCase):
    def test_config_is_standard_library_readable_yaml_subset(self) -> None:
        config_path = (
            ROOT / "configs" / "proper_v2" / "toolsandbox_feasibility.yaml"
        )
        parsed = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertEqual(parsed, load_config(config_path))

    def test_insufficient_information_module_default_is_applied(self) -> None:
        work = ROOT / "work"
        work.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=work) as directory:
            path = Path(directory) / "insufficient_information_scenarios.py"
            path.write_text(
                "ScenarioExtension(name='example', categories=[])\n",
                encoding="utf-8",
            )
            records = scenario_extensions(path)
        self.assertEqual(
            records[0]["categories"], ["INSUFFICIENT_INFORMATION"]
        )

    def test_summary_keeps_policy_types_separate(self) -> None:
        records = [
            {
                "name": "prerequisite",
                "categories": ["STATE_DEPENDENCY"],
                "tools": ["get_status", "set_status"],
                "offline_eligible": True,
            },
            {
                "name": "ask",
                "categories": ["INSUFFICIENT_INFORMATION"],
                "tools": ["search"],
                "offline_eligible": True,
            },
        ]
        summary = summarize(load_config(), records)
        self.assertEqual(summary["operation_capacity"]["invoke_prerequisite"], 1)
        self.assertEqual(
            summary["operation_capacity"]["request_information_or_stop"], 1
        )
        self.assertEqual(summary["operation_capacity"]["switch_tool"], 0)
        self.assertEqual(summary["operation_capacity"]["use_fallback"], 0)

    def test_pinned_checkout_reproduces_frozen_static_counts(self) -> None:
        repository = ROOT / "external" / "toolsandbox"
        if not repository.is_dir():
            self.skipTest("pinned ToolSandbox checkout is not present")
        result = run_audit()
        self.assertEqual(result["summary"]["scenario_extension_count"], 129)
        self.assertEqual(
            result["summary"]["offline_state_dependency_count"], 13
        )
        self.assertEqual(
            result["summary"]["offline_insufficient_information_count"], 18
        )
        self.assertFalse(result["all_readiness_checks_met"])
        self.assertEqual(
            result["planning_decision"]["next_action"],
            "stop_or_narrow_toolsandbox_scope",
        )
        self.assertFalse(result["boundary"]["model_loaded"])
        self.assertFalse(result["boundary"]["external_api_called"])
        self.assertFalse(result["boundary"]["gpu_run_authorized"])

    def test_dynamic_pilot_source_identity_and_boundary_are_frozen(self) -> None:
        repository = ROOT / "external" / "toolsandbox"
        if not repository.is_dir():
            self.skipTest("pinned ToolSandbox checkout is not present")
        config = load_dynamic_config()
        count, digest = python_source_manifest(repository)
        self.assertEqual(
            count, config["repository"]["python_source_file_count"]
        )
        self.assertEqual(
            digest, config["repository"]["python_source_manifest_sha256"]
        )
        self.assertFalse(config["boundary"]["scenario_played"])
        self.assertFalse(config["boundary"]["model_loaded"])
        self.assertFalse(config["boundary"]["gpu_run_authorized"])
        self.assertFalse(config["boundary"]["confirmatory_claim_authorized"])

    def test_dynamic_pilot_family_normalization_does_not_count_variants(self) -> None:
        expected = "send_message_with_contact_content_cellular_off"
        self.assertEqual(
            semantic_family(
                "send_message_with_contact_content_cellular_off"
                "_multiple_user_turn_alt"
            ),
            expected,
        )

    def test_scripted_smoke_freezes_evaluator_scope_and_boundaries(self) -> None:
        config = load_scripted_smoke_config()
        self.assertEqual(
            config["cases"]["state_dependency"]["scenario_name"],
            "turn_on_wifi_low_battery_mode",
        )
        self.assertEqual(
            config["cases"]["insufficient_information"]["scenario_name"],
            "find_days_till_holiday_insufficient_information",
        )
        self.assertFalse(
            config["cases"]["insufficient_information"][
                "native_metric_expected_to_distinguish_ask_from_silent_stop"
            ]
        )
        self.assertTrue(config["boundary"]["scripted_actions_only"])
        self.assertFalse(config["boundary"]["model_loaded"])
        self.assertFalse(config["boundary"]["gpu_run_authorized"])
        self.assertFalse(config["boundary"]["selector_effect_claim_authorized"])

    def test_selector_capacity_inputs_and_family_split_are_frozen(self) -> None:
        config = load_selector_capacity_config()
        for value in config["inputs"].values():
            self.assertTrue(resolve_and_verify_input(value).is_file())
        source = set(config["source_families"])
        target = set(config["target_profiles"])
        self.assertFalse(source & target)
        inventory = json.loads(
            (
                ROOT
                / "outputs"
                / "proper_v2"
                / "toolsandbox_dynamic_pilot"
                / "inventory.json"
            ).read_text(encoding="utf-8")
        )
        target_records = [
            record
            for record in inventory["records"]
            if record["semantic_family"] in target
        ]
        self.assertEqual(len(target_records), 14)
        self.assertFalse(config["boundary"]["gpu_run_authorized"])

    def test_selector_capacity_uses_six_frozen_legacy_memories(self) -> None:
        config = load_selector_capacity_config()
        manifest_path = resolve_and_verify_input(
            config["inputs"]["legacy_selection_manifest"]
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        experiences, definitions = configured_legacy_memories(config, manifest)
        self.assertEqual(len(experiences), 6)
        self.assertEqual(set(definitions), set(config["legacy_memory_ids"]))

    def test_selector_capacity_gate_requires_cross_policy_changes(self) -> None:
        config = load_selector_capacity_config()
        records = []
        for index in range(14):
            changed = index < 6
            records.append(
                {
                    "selection_changed": changed,
                    "selected_experience_id": f"memory-{index % 2}",
                    "selected_operation": (
                        "invoke_prerequisite"
                        if index % 2
                        else "stop_and_report"
                    ),
                    "semantic_family": f"family-{index % 4}",
                    "target_policy_type": (
                        "invoke_prerequisite"
                        if index < 4
                        else "stop_and_report"
                    ),
                    "rank1_operation": "retry_same_action",
                }
            )
        summary = summarize_selector_capacity(records, config)
        self.assertTrue(summary["future_model_pilot_preparation_authorized"])
        self.assertFalse(summary["gpu_run_authorized"])

    def test_action_memory_preparation_rule_and_inputs_are_frozen(self) -> None:
        config = load_action_memory_config()
        for value in config["inputs"].values():
            self.assertTrue(resolve_action_memory_input(value).is_file())
        self.assertEqual(
            config["derivation_rule"]["unit"],
            "causally_necessary_recovery_action",
        )
        self.assertFalse(
            config["derivation_rule"]["include_failed_goal_action"]
        )
        self.assertEqual(len(config["source_trajectories"]), 2)
        self.assertFalse(config["boundary"]["model_loaded"])
        self.assertFalse(config["boundary"]["gpu_run_authorized"])

    def test_action_memory_behavior_signature_deduplicates_sources(self) -> None:
        left = {
            "tool": "set_low_battery_mode_status",
            "arguments": {"on": False},
        }
        right = {
            "tool": "set_low_battery_mode_status",
            "arguments": {"on": False},
            "source_family": "a_different_source",
        }
        different = {
            "tool": "set_wifi_status",
            "arguments": {"on": True},
        }
        self.assertEqual(behavior_signature(left), behavior_signature(right))
        self.assertNotEqual(behavior_signature(left), behavior_signature(different))

    def test_behavioral_capacity_target_count_and_split_are_frozen(self) -> None:
        config = load_behavioral_capacity_config()
        inventory = json.loads(
            (
                ROOT
                / "outputs"
                / "proper_v2"
                / "toolsandbox_dynamic_pilot"
                / "inventory.json"
            ).read_text(encoding="utf-8")
        )
        target = set(config["target_profiles"])
        records = [
            record
            for record in inventory["records"]
            if record["semantic_family"] in target
        ]
        self.assertEqual(len(records), 19)
        self.assertFalse(set(config["source_families"]) & target)
        self.assertEqual(config["retrieval"]["top_k"], 12)
        self.assertFalse(config["boundary"]["gpu_run_authorized"])

    def test_stop_reason_change_is_not_an_intervention_change(self) -> None:
        first = SimpleNamespace(
            recovery_operation=RecoveryOperation.STOP_AND_REPORT,
            proposed_action=None,
            continuation_policy=ContinuationPolicy.TERMINATE,
            stop_conditions=("reason:a",),
        )
        second = SimpleNamespace(
            recovery_operation=RecoveryOperation.STOP_AND_REPORT,
            proposed_action=None,
            continuation_policy=ContinuationPolicy.TERMINATE,
            stop_conditions=("reason:b",),
        )
        self.assertEqual(
            intervention_signature(first), intervention_signature(second)
        )
        self.assertNotEqual(
            full_behavior_signature(first), full_behavior_signature(second)
        )

    def test_behavioral_capacity_gate_requires_action_diversity(self) -> None:
        config = load_behavioral_capacity_config()
        records = []
        tools = ["set_wifi_status", "set_cellular_service_status", "set_low_battery_mode_status"]
        for index in range(19):
            intervention = index < 12
            selected_operation = (
                "invoke_prerequisite" if index < 9 else "stop_and_report"
            )
            records.append(
                {
                    "selection_changed": intervention,
                    "operation_changed": intervention,
                    "intervention_distinct": intervention,
                    "full_behavior_distinct": intervention,
                    "semantic_family": f"family-{index % 5}",
                    "selected_operation": selected_operation,
                    "selected_proposed_action": (
                        {"tool_name": tools[index % 3], "arguments": {}}
                        if selected_operation == "invoke_prerequisite"
                        else None
                    ),
                    "selected_experience_id": f"memory-{index % 4}",
                    "target_policy_type": selected_operation,
                    "rank1_operation": "retry_same_action",
                }
            )
        summary = summarize_behavioral_capacity(records, config)
        self.assertTrue(summary["future_model_pilot_preparation_authorized"])
        self.assertEqual(summary["intervention_distinct_count"], 12)
        self.assertFalse(summary["gpu_run_authorized"])

    def test_phase_aware_capacity_sources_and_mapping_are_frozen(self) -> None:
        config = load_phase_aware_capacity_config()
        self.assertTrue(
            resolve_phase_aware_source(
                config["base_behavioral_capacity_config"]
            ).is_file()
        )
        for value in config["method_sources"].values():
            self.assertTrue(resolve_phase_aware_source(value).is_file())
        self.assertEqual(
            config["phase_mapping"],
            {
                "invoke_prerequisite": "post_failure",
                "stop_and_report": "pre_action",
            },
        )
        self.assertFalse(config["boundary"]["gpu_run_authorized"])

    def test_phase_aware_target_has_no_synthetic_pre_action_failure(self) -> None:
        stop = phase_aware_target(
            instruction="Find reminders created yesterday.",
            tools=["end_conversation", "search_reminder"],
            profile={
                "policy_type": "stop_and_report",
                "failed_tool": "search_reminder",
                "error_code": "insufficient_information",
                "evidence_codes": [
                    "failure_state:insufficient_information"
                ],
            },
        )
        self.assertEqual(stop.phase.value, "pre_action")
        self.assertIsNone(stop.error_code)
        self.assertEqual(stop.repeated_same_call_count, 0)
        prerequisite = phase_aware_target(
            instruction="Turn on location.",
            tools=[
                "set_location_service_status",
                "set_low_battery_mode_status",
            ],
            profile={
                "policy_type": "invoke_prerequisite",
                "failed_tool": "set_location_service_status",
                "failed_arguments": {"on": True},
                "error_code": "permission_error",
                "evidence_codes": ["error_code:permission_error"],
            },
        )
        self.assertEqual(prerequisite.phase.value, "post_failure")
        self.assertEqual(prerequisite.error_code, "permission_error")
        self.assertEqual(prerequisite.repeated_same_call_count, 1)


if __name__ == "__main__":
    unittest.main()
