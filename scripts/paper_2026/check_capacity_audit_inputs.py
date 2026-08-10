from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

REQUIRED_RAW_INPUTS = (
    {
        "path": "work/toolmisusebench_sample/dev.jsonl",
        "sha256": "a5a2b49b28c66f01bdbac37966c00cca9c6a1027a6d4b5b3a8c1d1d359db27e3",
        "role": "frozen_development_memory_sources",
    },
    {
        "path": "work/toolmisusebench_test/test_public.jsonl",
        "sha256": "12c5e1e93926f4089dfc8d0c60cea53b556057360562375510744858fc6f1161",
        "bytes": 1_695_141,
        "role": "three_stratum_public_targets",
    },
)

HISTORICAL_CONTEXTS = (
    {
        "path": "work/confirmatory_gate_v1_prepared.json",
        "list_key": "records",
        "expected_count": 189,
        "stratum": "argument_omission",
    },
    {
        "path": "outputs/proper_v1/transient_authz_capacity_v1/screening.json",
        "list_key": "records",
        "expected_count": 175,
        "stratum": "transient_authorization",
    },
    {
        "path": "outputs/proper_v2/timeout_capacity_v2/screening.json",
        "list_key": "records",
        "expected_count": 177,
        "stratum": "timeout",
    },
    {
        "path": "work/memory_bank_prepared.json",
        "list_key": "memory_sources",
        "expected_count": 100,
        "stratum": "frozen_memory_bank",
    },
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inspect_raw_input(root: Path, spec: dict[str, Any]) -> dict[str, Any]:
    path = root / str(spec["path"])
    result = {
        "path": spec["path"],
        "role": spec["role"],
        "expected_sha256": spec["sha256"],
        "present": path.is_file(),
        "verified": False,
    }
    if not path.is_file():
        return result
    actual_hash = sha256_file(path)
    result.update({"bytes": path.stat().st_size, "sha256": actual_hash})
    hash_ok = actual_hash == spec["sha256"]
    bytes_ok = "bytes" not in spec or path.stat().st_size == spec["bytes"]
    result["verified"] = hash_ok and bytes_ok
    return result


def inspect_historical_context(root: Path, spec: dict[str, Any]) -> dict[str, Any]:
    path = root / str(spec["path"])
    result = {
        "path": spec["path"],
        "stratum": spec["stratum"],
        "expected_count": spec["expected_count"],
        "present": path.is_file(),
        "verified": False,
    }
    if not path.is_file():
        return result
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        records = payload[spec["list_key"]]
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as error:
        result["error"] = f"{type(error).__name__}: {error}"
        return result
    count = len(records) if isinstance(records, list) else None
    result.update(
        {
            "count": count,
            "sha256": sha256_file(path),
            "verified": count == spec["expected_count"],
        }
    )
    return result


def audit_capacity_inputs(root: Path = ROOT) -> dict[str, Any]:
    raw_inputs = [inspect_raw_input(root, spec) for spec in REQUIRED_RAW_INPUTS]
    contexts = [
        inspect_historical_context(root, spec) for spec in HISTORICAL_CONTEXTS
    ]
    missing_or_invalid = [
        item["path"] for item in raw_inputs + contexts if not item["verified"]
    ]
    ready = not missing_or_invalid
    return {
        "schema_version": 1,
        "run_kind": "paper_2026_capacity_audit_input_preflight",
        "boundary": {
            "model_loaded": False,
            "model_outputs_generated": False,
            "historical_context_only": True,
        },
        "raw_inputs": raw_inputs,
        "historical_contexts": contexts,
        "summary": {
            "status": "ready" if ready else "blocked_missing_or_invalid_inputs",
            "ready_for_offline_capacity_audit": ready,
            "missing_or_invalid_paths": missing_or_invalid,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify non-model inputs required by the three-stratum selector capacity audit."
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-ready", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = audit_capacity_inputs(args.root.resolve())
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = args.output
        if not output.is_absolute():
            output = args.root / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    if args.require_ready and not payload["summary"]["ready_for_offline_capacity_audit"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
