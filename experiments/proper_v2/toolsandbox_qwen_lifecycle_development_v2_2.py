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
CONFIG = (
    ROOT
    / "configs"
    / "proper_v2"
    / "toolsandbox_qwen_lifecycle_development_v2_2.yaml"
)
sys.path.insert(0, str(ROOT / "experiments" / "proper_v2"))

import lifecycle_development_v2_2 as lifecycle  # noqa: E402
import toolsandbox_lifecycle_development_v2_2 as scripted  # noqa: E402
import toolsandbox_model_pilot_runner_validation_v2_1 as engine  # noqa: E402
from toolsandbox_qwen_pilot_v2_1 import parse_model_decision  # noqa: E402


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("status") != (
        "frozen_qwen_lifecycle_development_before_model_outputs"
    ):
        raise RuntimeError("v2.2 Qwen development config status is invalid")
    boundary = config["boundary"]
    if (
        not boundary["gpu_development_run_authorized"]
        or boundary["confirmatory_claim_authorized"]
        or boundary["heldout_claim_authorized"]
    ):
        raise RuntimeError("v2.2 Qwen run must remain development-only")
    for item in config["frozen_inputs"].values():
        target = ROOT / str(item["path"])
        observed = lifecycle.sha256_file(target)
        if observed != str(item["sha256"]):
            raise RuntimeError(
                f"v2.2 Qwen frozen input mismatch: {target}; "
                f"expected={item['sha256']} observed={observed}"
            )
    return config


class JsonlWorkerClient:
    def __init__(self, config: Mapping[str, Any]) -> None:
        model = config["model"]
        python = Path(str(model["python"]))
        script = ROOT / str(model["worker_script"])
        model_path = Path(str(model["model_path"]))
        if not python.is_file():
            raise RuntimeError(f"Qwen environment Python is missing: {python}")
        if not script.is_file():
            raise RuntimeError(f"Qwen worker is missing: {script}")
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
            raise RuntimeError("failed to create Qwen worker pipes")
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
        usage = response["usage"]
        self.requests.append(
            {
                "request_id": request["request_id"],
                "request_sha256": engine.sha256_text(engine.canonical(request)),
                "response_sha256": engine.sha256_text(
                    engine.canonical(response)
                ),
                "prompt_token_count": int(usage["prompt_token_count"]),
                "completion_token_count": int(
                    usage["completion_token_count"]
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

    def __enter__(self) -> "JsonlWorkerClient":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()


class LifecycleQwenProvider:
    def __init__(
        self,
        *,
        client: JsonlWorkerClient,
        config: Mapping[str, Any],
    ) -> None:
        self.client = client
        self.config = config
        self.policy = lifecycle.lifecycle_policy(
            lifecycle.load_config(
                ROOT
                / str(
                    config["frozen_inputs"]["scripted_lifecycle_config"][
                        "path"
                    ]
                )
            )
        )
        self.call_count = 0

    @staticmethod
    def visible_history(
        history: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return [
            {
                "tool_name": item["tool_name"],
                "arguments": item["arguments"],
                "result": item["result"],
                "exception": item["exception"],
            }
            for item in history
        ]

    @staticmethod
    def lifecycle_messages(
        initial: Mapping[str, Any],
        payload: Mapping[str, Any],
    ) -> list[dict[str, str]]:
        messages = copy.deepcopy(initial["messages"])
        messages[0]["content"] += (
            " Obey MEMORY_LIFECYCLE_STATE. An active memory may guide only "
            "its bounded recovery operation. When consumed, do not repeat its "
            "action; resume the original task using ordinary planning."
        )
        lines = [
            line
            for line in messages[-1]["content"].splitlines()
            if not line.startswith("RETRIEVED_MEMORY=")
        ]
        lines.insert(
            max(0, len(lines) - 2),
            "MEMORY_LIFECYCLE_STATE=" + engine.canonical(payload),
        )
        messages[-1]["content"] = "\n".join(lines)
        return messages

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
        memory = None
        state = None
        if condition == "proper_v2_1_memory":
            memory, state = lifecycle.state_from_history(
                record,
                branch_history,
                self.policy,
            )
            messages = self.lifecycle_messages(
                initial,
                lifecycle.lifecycle_prompt_payload(state, memory),
            )
            label = "proper_v2_2_lifecycle_memory"
        else:
            messages = copy.deepcopy(initial["messages"])
            label = condition
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
        request_id = f"{record['pair_id']}:{label}:step-{decision_index:02d}"
        request = {
            "request_id": request_id,
            "messages": messages,
            "seed": int(self.config["model"]["seed"]),
            "max_new_tokens": int(self.config["model"]["max_new_tokens"]),
        }
        response = self.client.complete(request)
        proposed, valid, error = parse_model_decision(
            str(response["raw_text"]),
            available_tools=set(
                str(value) for value in record["available_tool_names"]
            ),
        )
        decision = dict(proposed)
        controller = {
            "guard_applied": condition == "proper_v2_1_memory",
            "decision_allowed": True,
            "reason_code": "lifecycle_not_applicable_to_baseline",
            "model_proposed_decision": dict(proposed),
        }
        if memory is not None and state is not None:
            allowed, reason = lifecycle.guard_decision(
                state,
                memory,
                proposed,
            )
            controller.update(
                {
                    "decision_allowed": allowed,
                    "reason_code": reason,
                }
            )
            if not allowed:
                decision = {
                    "kind": "stop",
                    "reason_code": reason,
                    "message": "The memory lifecycle blocked another tool call.",
                }
            if decision["kind"] == "stop":
                state = lifecycle.advance_lifecycle(
                    state,
                    memory,
                    lifecycle.LifecycleObservation(
                        phase=state.phase,
                        agent_stop_reason=str(decision["reason_code"]),
                    ),
                    self.policy,
                )
            decision["_lifecycle"] = state.to_mapping()
            decision["_lifecycle_prompt_sha256"] = engine.sha256_text(
                engine.canonical(
                    lifecycle.lifecycle_prompt_payload(state, memory)
                )
            )
        decision["_controller"] = controller
        decision["_model"] = {
            "request_id": request_id,
            "request_sha256": engine.sha256_text(engine.canonical(request)),
            "raw_text": str(response["raw_text"]),
            "valid_json_decision": valid,
            "parse_error": error,
            "usage": dict(response["usage"]),
        }
        print(
            "MODEL_PROGRESS="
            f"{self.call_count} request={request_id} "
            f"valid_json={str(valid).lower()} kind={decision['kind']}",
            file=sys.stderr,
            flush=True,
        )
        return decision


def condition_model_decisions_valid(record: Mapping[str, Any]) -> bool:
    return all(
        bool(decision.get("_model", {}).get("valid_json_decision"))
        for condition in record["conditions"].values()
        for decision in condition["decisions"]
    )


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    phase_summary = {}
    for phase in ("pre_action", "post_failure"):
        subset = [item for item in records if item["decision_phase"] == phase]
        phase_summary[phase] = {}
        for source_name, report_name in (
            ("tfidf_rank1_memory", "tfidf_rank1_memory"),
            ("proper_v2_1_memory", "proper_v2_2_lifecycle_memory"),
        ):
            conditions = [item["conditions"][source_name] for item in subset]
            phase_summary[phase][report_name] = {
                "mean_similarity": sum(
                    item["evaluation"]["similarity"] for item in conditions
                )
                / len(conditions),
                "task_completion_count": sum(
                    item["evaluation"]["similarity"] == 1.0
                    for item in conditions
                ),
                "first_decision_alignment_count": sum(
                    item["first_decision_policy_alignment"]
                    for item in conditions
                ),
                "minefield_condition_count": sum(
                    item["evaluation"]["minefield_similarity"] > 0
                    for item in conditions
                ),
                "tool_exception_count": sum(
                    item["tool_exception_count"] for item in conditions
                ),
                "repeated_identical_tool_call_count": sum(
                    item["repeated_identical_tool_call_count"]
                    for item in conditions
                ),
                "model_decision_count": sum(
                    item["recovery_decision_count"] for item in conditions
                ),
                "tool_call_count": sum(
                    item["recovery_tool_call_count"] for item in conditions
                ),
                "prompt_token_count": sum(
                    int(decision["_model"]["usage"]["prompt_token_count"])
                    for item in conditions
                    for decision in item["decisions"]
                ),
                "completion_token_count": sum(
                    int(
                        decision["_model"]["usage"][
                            "completion_token_count"
                        ]
                    )
                    for item in conditions
                    for decision in item["decisions"]
                ),
            }
    decisions = [
        decision
        for record in records
        for condition in record["conditions"].values()
        for decision in condition["decisions"]
    ]
    lifecycle_decisions = [
        decision
        for record in records
        for decision in record["conditions"]["proper_v2_1_memory"][
            "decisions"
        ]
    ]
    return {
        "pair_count": len(records),
        "condition_count": sum(len(item["conditions"]) for item in records),
        "phase_counts": dict(
            sorted(Counter(item["decision_phase"] for item in records).items())
        ),
        "all_condition_starts_identical": all(
            item["identical_condition_start"] for item in records
        ),
        "valid_json_decision_count": sum(
            bool(item["_model"]["valid_json_decision"]) for item in decisions
        ),
        "invalid_json_decision_count": sum(
            not bool(item["_model"]["valid_json_decision"])
            for item in decisions
        ),
        "controller_guard_block_count": sum(
            item["_controller"]["guard_applied"]
            and not item["_controller"]["decision_allowed"]
            for item in lifecycle_decisions
        ),
        "phase_summary": phase_summary,
    }


def run_development(config_path: Path = CONFIG) -> dict[str, Any]:
    config = load_config(config_path)
    print("STAGE=scripted_lifecycle_validation", file=sys.stderr, flush=True)
    scripted_result = scripted.dynamic_validation(
        ROOT
        / str(
            config["frozen_inputs"]["scripted_lifecycle_config"]["path"]
        )
    )
    if not scripted_result["passed"]:
        raise RuntimeError(
            "same-process scripted lifecycle validation failed; GPU not started"
        )
    runner_config = ROOT / str(
        config["frozen_inputs"]["v2_1_runner_config"]["path"]
    )
    manifest_config = lifecycle.load_config(
        ROOT
        / str(
            config["frozen_inputs"]["scripted_lifecycle_config"]["path"]
        )
    )
    manifest = lifecycle.load_manifest(manifest_config)
    pair_order = [str(item["pair_id"]) for item in manifest["records"]]
    smoke_pair = str(config["execution"]["smoke_pair_id"])
    print("STAGE=load_qwen_worker", file=sys.stderr, flush=True)
    with JsonlWorkerClient(config) as client:
        provider = LifecycleQwenProvider(client=client, config=config)
        print(f"STAGE=gpu_smoke pair={smoke_pair}", file=sys.stderr, flush=True)
        smoke = engine.run_validation(
            runner_config,
            decision_provider=provider,
            pair_ids={smoke_pair},
        )
        smoke_passed = (
            len(smoke["records"]) == 1
            and condition_model_decisions_valid(smoke["records"][0])
            and smoke["records"][0]["identical_condition_start"]
        )
        if not smoke_passed:
            return {
                "schema_version": 1,
                "run_kind": "proper_v2_2_qwen_lifecycle_smoke_stopped",
                "smoke_passed": False,
                "full_development_completed": False,
                "scripted_lifecycle_summary": scripted_result["summary"],
                "smoke_records": smoke["records"],
                "model_request_log": client.requests,
                "boundary": dict(config["boundary"]),
            }
        remaining = set(pair_order) - {smoke_pair}
        print("STAGE=full_development remaining_pairs=11", file=sys.stderr, flush=True)
        remainder = engine.run_validation(
            runner_config,
            decision_provider=provider,
            pair_ids=remaining,
        )
        by_id = {
            str(item["pair_id"]): item
            for item in smoke["records"] + remainder["records"]
        }
        records = [by_id[pair_id] for pair_id in pair_order]
        summary = summarize(records)
        completed = (
            summary["pair_count"] == int(config["execution"]["pair_count"])
            and summary["condition_count"]
            == int(config["execution"]["condition_count"])
            and summary["all_condition_starts_identical"]
            and summary["invalid_json_decision_count"] == 0
        )
        return {
            "schema_version": 1,
            "run_kind": "proper_v2_2_toolsandbox_qwen_lifecycle_development",
            "identities": {
                "config_sha256": lifecycle.sha256_file(config_path),
                "frozen_input_sha256": {
                    name: str(item["sha256"])
                    for name, item in config["frozen_inputs"].items()
                },
            },
            "smoke_pair_id": smoke_pair,
            "smoke_passed": True,
            "full_development_completed": completed,
            "scripted_lifecycle_summary": scripted_result["summary"],
            "summary": summary,
            "records": records,
            "model_request_log": client.requests,
            "model_protocol": dict(config["model"]),
            "boundary": dict(config["boundary"]),
            "interpretation_limits": {
                "v2_1_pairs_are_development_only": True,
                "selector_first_step_reported_separately": True,
                "memory_lifecycle_reported_separately": True,
                "final_task_completion_reported_separately": True,
                "safety_reported_separately": True,
                "cost_reported_separately": True,
                "confirmatory_claim_not_authorized": True,
                "all_agent_memory_generalization_not_authorized": True,
            },
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the frozen PROPER v2.2 Qwen lifecycle development pilot."
    )
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    config = load_config(args.config)
    result = run_development(args.config)
    output = args.output or ROOT / str(config["output"]["path"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "run_kind",
                    "smoke_pair_id",
                    "smoke_passed",
                    "full_development_completed",
                    "summary",
                    "interpretation_limits",
                )
                if key in result
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    print(f"OUTPUT={output}")
    status = "PASS" if result.get("full_development_completed") else "STOP"
    print(f"RESULT={status}_PROPER_V2_2_QWEN_LIFECYCLE_DEVELOPMENT")
    return 0 if result.get("full_development_completed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
