"""Model-free traces for the controlled AppWorld protected-code boundary."""

from __future__ import annotations

from typing import Any


def run_traces() -> list[dict[str, Any]]:
    return [
        {
            "trace_id": "exact_apps_bundle_aggregate_only",
            "input": "exact_apps_bundle",
            "decision": "allow_in_memory_inventory_after_implementation_gate",
            "decrypted": False,
            "extracted": False,
            "protected_plaintext_persisted": False,
        },
        {
            "trace_id": "tests_bundle_proposal",
            "input": "tests_bundle",
            "decision": "stop_protocol_boundary",
            "decrypted": False,
            "extracted": False,
            "protected_plaintext_persisted": False,
        },
        {
            "trace_id": "unsafe_member_path",
            "input": "decrypted_zip_with_parent_path",
            "decision": "stop_without_extraction",
            "decrypted": False,
            "extracted": False,
            "protected_plaintext_persisted": False,
        },
        {
            "trace_id": "duplicate_or_symlink_member",
            "input": "decrypted_zip_with_ambiguous_member",
            "decision": "stop_without_extraction",
            "decrypted": False,
            "extracted": False,
            "protected_plaintext_persisted": False,
        },
        {
            "trace_id": "plaintext_path_output",
            "input": "result_contains_protected_member_name",
            "decision": "stop_privacy_boundary",
            "decrypted": False,
            "extracted": False,
            "protected_plaintext_persisted": False,
        },
        {
            "trace_id": "official_install_or_data_download",
            "input": "appworld_install_or_download_data",
            "decision": "stop_protocol_boundary",
            "decrypted": False,
            "extracted": False,
            "protected_plaintext_persisted": False,
        },
    ]
