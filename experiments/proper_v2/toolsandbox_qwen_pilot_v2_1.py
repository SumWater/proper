from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs" / "proper_v2" / "toolsandbox_qwen_pilot_v2_1.yaml"
sys.path.insert(0, str(ROOT / "experiments" / "proper_v2"))

import toolsandbox_model_pilot_runner_validation_v2_1 as engine  # noqa: E402


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("status") != (
        "frozen_exploratory_qwen_pilot_before_model_outputs"
    ):
        raise RuntimeError("Qwen pilot config status is invalid")
    if not config["boundary"]["gpu_exploratory_pilot_authorized"]:
        raise RuntimeError("exploratory GPU pilot is not authorized")
    if config["evaluation"]["confirmatory_test_authorized"]:
        raise RuntimeError("exploratory pilot cannot authorize confirmation")
    frozen = config["prepared_manifest"]
    manifest_path = ROOT / str(frozen["path"])
    if engine.sha256_file(manifest_path) != str(frozen["sha256"]):
        raise RuntimeError("Qwen pilot prepared-manifest hash mismatch")
    validation = config["runner_validation"]
    for path_key, hash_key in (
        ("config", "config_sha256"),
        ("source", "source_sha256"),
    ):
        path_value = ROOT / str(validation[path_key])
        if engine.sha256_file(path_value) != str(validation[hash_key]):
            raise RuntimeError(
                f"Qwen pilot frozen validation {path_key} hash mismatch"
            )
    worker = ROOT / str(config["model"]["worker_script"])
    if engine.sha256_file(worker) != str(
        config["model"]["worker_script_sha256"]
    ):
        raise RuntimeError("Qwen pilot frozen worker hash mismatch")
    return config


def parse_model_decision(
    raw_text: str,
    *,
    available_tools: set[str],
) -> tuple[dict[str, Any], bool, str | None]:
    try:
        payload = json.loads(raw_text)
        if not isinstance(payload, Mapping):
            raise ValueError("model output must be one JSON object")
        kind = str(payload["kind"])
        if kind == "tool":
            tool_name = str(payload["tool_name"])
            arguments = payload["arguments"]
            if tool_name not in available_tools:
                raise ValueError(f"unavailable tool: {tool_name}")
            if not isinstance(arguments, Mapping):
                raise ValueError("tool arguments must be an object")
            return (
                {
                    "kind": "tool",
                    "tool_name": tool_name,
                    "arguments": dict(arguments),
                },
                True,
                None,
            )
        if kind == "stop":
            return (
                {
                    "kind": "stop",
                    "reason_code": str(payload["reason_code"]),
                    "message": str(payload.get("message", "")),
                },
                True,
                None,
            )
        raise ValueError("kind must be tool or stop")
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        return (
            {
                "kind": "stop",
                "reason_code": "invalid_model_output",
                "message": "",
            },
            False,
            f"{type(exc).__name__}: {exc}",
        )


class JsonlWorkerClient:
    def __init__(self, config: Mapping[str, Any]) -> None:
        model = config["model"]
        python = Path(str(model["python"]))
        script = ROOT / str(model["worker_script"])
        model_path = Path(str(model["model_path"]))
        if not python.is_file():
            raise RuntimeError(f"Qwen environment Python is missing: {python}")
        if not script.is_file():
            raise RuntimeError(f"Qwen worker script is missing: {script}")
        if not model_path.is_dir():
            raise RuntimeError(f"Qwen model directory is missing: {model_path}")
        environment = os.environ.copy()
        environment["CUDA_VISIBLE_DEVICES"] = str(
            model["cuda_visible_devices"]
        )
        self.process = subprocess.Popen(
            [
                str(python),
                "-u",
                str(script),
                "--model-path",
                str(model_path),
            ],
            cwd=str(ROOT),
            env=environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        if self.process.stdin is None or self.process.stdout is None:
            raise RuntimeError("failed to create Qwen worker JSONL pipes")
        self.requests: list[dict[str, Any]] = []

    def complete(self, request: Mapping[str, Any]) -> dict[str, Any]:
        if self.process.poll() is not None:
            raise RuntimeError(
                f"Qwen worker exited early with code {self.process.returncode}"
            )
        line = json.dumps(request, ensure_ascii=False, sort_keys=True)
        self.process.stdin.write(line + "\n")
        self.process.stdin.flush()
        response_line = self.process.stdout.readline()
        if not response_line:
            raise RuntimeError("Qwen worker closed stdout without a response")
        response = json.loads(response_line)
        if response.get("request_id") != request["request_id"]:
            raise RuntimeError("Qwen worker response request_id mismatch")
        if not response.get("ok"):
            raise RuntimeError(f"Qwen worker request failed: {response}")
        self.requests.append(
            {
                "request_id": request["request_id"],
                "request_sha256": engine.sha256_text(engine.canonical(request)),
                "response_sha256": engine.sha256_text(
                    engine.canonical(response)
                ),
            }
        )
        return dict(response)

    def close(self) -> None:
        if self.process.stdin is not None:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            self.process.wait(timeout=10)

    def __enter__(self) -> JsonlWorkerClient:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()


class QwenDecisionProvider:
    def __init__(
        self,
        *,
        client: JsonlWorkerClient,
        config: Mapping[str, Any],
    ) -> None:
        self.client = client
        self.config = config
        self.call_count = 0

    @staticmethod
    def visible_history(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "tool_name": item["tool_name"],
                "arguments": item["arguments"],
                "result": item["result"],
                "exception": item["exception"],
            }
            for item in history
        ]

    def decide(
        self,
        *,
        record: Mapping[str, Any],
        condition: str,
        branch_history: list[dict[str, Any]],
        prefix_history: list[dict[str, Any]],
        decision_index: int,
        decisions_left: int,
        tool_calls_left: int,
    ) -> dict[str, Any]:
        self.call_count += 1
        initial = record["conditions"][condition]["initial_request"]
        messages = copy.deepcopy(initial["messages"])
        runtime = {
            "visible_prefix_history": self.visible_history(prefix_history),
            "visible_recovery_history": self.visible_history(branch_history),
            "decision_index": decision_index,
            "remaining_budget": {
                "decisions_left": decisions_left,
                "tool_calls_left": tool_calls_left,
            },
        }
        messages[-1]["content"] += (
            "\nRUNTIME_VISIBLE_HISTORY=" + engine.canonical(runtime)
        )
        request_id = (
            f"{record['pair_id']}:{condition}:step-{decision_index:02d}"
        )
        request = {
            "request_id": request_id,
            "messages": messages,
            "seed": int(self.config["model"]["seed"]),
            "max_new_tokens": int(self.config["model"]["max_new_tokens"]),
        }
        response = self.client.complete(request)
        decision, valid, error = parse_model_decision(
            str(response["raw_text"]),
            available_tools=set(
                str(value) for value in record["available_tool_names"]
            ),
        )
        print(
            "MODEL_PROGRESS="
            f"{self.call_count} request={request_id} "
            f"valid_json={str(valid).lower()} kind={decision['kind']}",
            file=sys.stderr,
            flush=True,
        )
        decision["_model"] = {
            "request_id": request_id,
            "request_sha256": engine.sha256_text(engine.canonical(request)),
            "raw_text": str(response["raw_text"]),
            "valid_json_decision": valid,
            "parse_error": error,
        }
        return decision


def condition_model_decisions_valid(record: Mapping[str, Any]) -> bool:
    return all(
        bool(decision.get("_model", {}).get("valid_json_decision"))
        for condition in record["conditions"].values()
        for decision in condition["decisions"]
    )


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    phase_summary = {}
    for phase in ("post_failure", "pre_action"):
        subset = [item for item in records if item["decision_phase"] == phase]
        tfidf = [
            item["conditions"]["tfidf_rank1_memory"]["evaluation"]["similarity"]
            for item in subset
        ]
        proper = [
            item["conditions"]["proper_v2_1_memory"]["evaluation"]["similarity"]
            for item in subset
        ]
        phase_summary[phase] = {
            "pair_count": len(subset),
            "tfidf_mean_similarity": sum(tfidf) / len(tfidf),
            "proper_mean_similarity": sum(proper) / len(proper),
            "proper_better_pair_count": sum(
                right > left for left, right in zip(tfidf, proper)
            ),
            "proper_worse_pair_count": sum(
                right < left for left, right in zip(tfidf, proper)
            ),
            "tie_pair_count": sum(
                right == left for left, right in zip(tfidf, proper)
            ),
        }
    all_decisions = [
        decision
        for record in records
        for condition in record["conditions"].values()
        for decision in condition["decisions"]
    ]
    return {
        "pair_count": len(records),
        "condition_count": sum(len(item["conditions"]) for item in records),
        "phase_counts": dict(
            sorted(Counter(item["decision_phase"] for item in records).items())
        ),
        "phase_summary": phase_summary,
        "all_condition_starts_identical": all(
            item["identical_condition_start"] for item in records
        ),
        "valid_json_decision_count": sum(
            bool(item.get("_model", {}).get("valid_json_decision"))
            for item in all_decisions
        ),
        "invalid_json_decision_count": sum(
            not bool(item.get("_model", {}).get("valid_json_decision"))
            for item in all_decisions
        ),
        "total_model_decision_count": len(all_decisions),
        "proper_first_decision_alignment_count": sum(
            item["conditions"]["proper_v2_1_memory"][
                "first_decision_policy_alignment"
            ]
            for item in records
        ),
        "tfidf_first_decision_alignment_count": sum(
            item["conditions"]["tfidf_rank1_memory"][
                "first_decision_policy_alignment"
            ]
            for item in records
        ),
        "proper_minefield_condition_count": sum(
            item["conditions"]["proper_v2_1_memory"]["evaluation"][
                "minefield_similarity"
            ]
            > 0.0
            for item in records
        ),
        "tfidf_minefield_condition_count": sum(
            item["conditions"]["tfidf_rank1_memory"]["evaluation"][
                "minefield_similarity"
            ]
            > 0.0
            for item in records
        ),
    }


def run_pilot(config_path: Path = CONFIG) -> dict[str, Any]:
    config = load_config(config_path)
    validation_config = ROOT / str(
        config["runner_validation"]["config"]
    )
    print(
        "STAGE=scripted_runner_validation",
        file=sys.stderr,
        flush=True,
    )
    validation = engine.run_validation(validation_config)
    if not validation["summary"]["runner_validation_passed"]:
        raise RuntimeError(
            "scripted runner validation failed in the same process; "
            "GPU model execution was not started"
        )

    _, manifest = engine.load_manifest(engine.load_config(validation_config))
    pair_order = [str(item["pair_id"]) for item in manifest["records"]]
    smoke_pair = str(config["execution"]["smoke_pair_id"])
    remaining = set(pair_order) - {smoke_pair}
    print(
        "STAGE=load_qwen_worker",
        file=sys.stderr,
        flush=True,
    )
    with JsonlWorkerClient(config) as client:
        provider = QwenDecisionProvider(client=client, config=config)
        print(
            f"STAGE=gpu_smoke pair={smoke_pair}",
            file=sys.stderr,
            flush=True,
        )
        smoke_engine = engine.run_validation(
            validation_config,
            decision_provider=provider,
            pair_ids={smoke_pair},
        )
        smoke_records = smoke_engine["records"]
        smoke_passed = (
            len(smoke_records) == 1
            and condition_model_decisions_valid(smoke_records[0])
            and smoke_records[0]["identical_condition_start"]
        )
        if not smoke_passed:
            return {
                "schema_version": 1,
                "run_kind": "proper_v2_1_toolsandbox_qwen_smoke_stopped",
                "identities": {
                    "config_sha256": engine.sha256_file(config_path),
                    "prepared_manifest_sha256": config["prepared_manifest"][
                        "sha256"
                    ],
                },
                "scripted_validation_summary": validation["summary"],
                "smoke_passed": False,
                "smoke_records": smoke_records,
                "full_pilot_completed": False,
                "model_request_log": client.requests,
                "boundary": dict(config["boundary"]),
            }
        print(
            "STAGE=full_pilot remaining_pairs=11",
            file=sys.stderr,
            flush=True,
        )
        remainder_engine = engine.run_validation(
            validation_config,
            decision_provider=provider,
            pair_ids=remaining,
        )
        by_id = {
            str(item["pair_id"]): item
            for item in smoke_records + remainder_engine["records"]
        }
        records = [by_id[pair_id] for pair_id in pair_order]
        summary = summarize(records)
        completed = (
            summary["pair_count"]
            == int(config["execution"]["full_pair_count"])
            and summary["condition_count"]
            == int(config["execution"]["full_condition_count"])
            and summary["all_condition_starts_identical"]
        )
        return {
            "schema_version": 1,
            "run_kind": "proper_v2_1_toolsandbox_qwen_exploratory_pilot",
            "identities": {
                "config_sha256": engine.sha256_file(config_path),
                "prepared_manifest_sha256": config["prepared_manifest"][
                    "sha256"
                ],
                "prepared_payload_sha256": config["prepared_manifest"][
                    "prepared_payload_sha256"
                ],
            },
            "scripted_validation_summary": validation["summary"],
            "smoke_pair_id": smoke_pair,
            "smoke_passed": True,
            "full_pilot_completed": completed,
            "summary": summary,
            "records": records,
            "model_request_log": list(client.requests),
            "model_protocol": dict(config["model"]),
            "boundary": dict(config["boundary"]),
            "interpretation_limits": {
                "exploratory_capacity_selected_pilot": True,
                "confirmatory_claim_not_authorized": True,
                "all_agent_memory_generalization_not_authorized": True,
                "phase_stratified_reporting_required": True,
                "raw_toolsandbox_scores_preserved": True,
            },
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the one-shot PROPER v2.1 ToolSandbox Qwen pilot."
    )
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    config = load_config(args.config)
    result = run_pilot(args.config)
    output = args.output or ROOT / str(config["output"]["path"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    compact = {
        key: result[key]
        for key in (
            "run_kind",
            "smoke_pair_id",
            "smoke_passed",
            "full_pilot_completed",
            "summary",
            "interpretation_limits",
        )
        if key in result
    }
    print(json.dumps(compact, ensure_ascii=False, indent=2, sort_keys=True))
    status = "PASS" if result.get("full_pilot_completed") else "STOP"
    print(f"RESULT={status}_PROPER_V2_1_TOOLSANDBOX_QWEN_PILOT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
