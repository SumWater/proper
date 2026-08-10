from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts" / "paper_2026")]

from failure_memory.paper_2026.llm_judge import (  # noqa: E402
    REQUIRED_CONTEXT_KEYS,
    JudgeCandidate,
    build_judge_messages,
    decide_with_rank1_fallback,
)
from smoke_agent_model import (  # noqa: E402
    gpu_snapshot,
    verify_sha256sum_manifest,
)


CONFIG = ROOT / "configs" / "paper_2026" / "e1_llm_judge_execution_v1_0.yaml"
FORBIDDEN_OBSERVABLE_KEYS = frozenset(
    {
        "stratum",
        "applicable",
        "applicability",
        "source_task_id",
        "instance_id",
        "experience_id",
        "provenance",
        "gold_action",
        "evaluator_outcome",
        "method_name",
        "condition_name",
    }
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_sha256(value: Any) -> str:
    rendered = json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return sha256_text(rendered)


def root_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def forbidden_key_paths(value: Any, path: str = "$") -> list[str]:
    failures: list[str] = []
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if str(key) in FORBIDDEN_OBSERVABLE_KEYS:
                failures.append(f"{path}.{key}")
            failures.extend(forbidden_key_paths(nested, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            failures.extend(forbidden_key_paths(nested, f"{path}[{index}]"))
    return failures


def load_checkpoint(path: Path, run_identity: str) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    records: dict[str, dict[str, Any]] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"invalid checkpoint JSON at line {line_number}") from error
        if record.get("run_identity_sha256") != run_identity:
            raise RuntimeError("checkpoint belongs to a different frozen run identity")
        target_key = str(record.get("target_key", ""))
        if not target_key or target_key in records:
            raise RuntimeError("checkpoint target keys are missing or duplicated")
        records[target_key] = record
    return records


def append_checkpoint(path: Path, record: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":"), sort_keys=True))
        handle.write("\n")
        handle.flush()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Frozen resumable E1 Qwen applicability-judge selection runner."
    )
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--physical-gpu-index", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = args.config.expanduser().resolve()
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    output = root_path(config["outputs"]["final"])
    checkpoint = root_path(config["outputs"]["checkpoint_jsonl"])
    payload: dict[str, Any] = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_kind": "paper_2026_e1_formal_offline_llm_judge_selection",
        "status": "initializing",
        "config_path": str(config_path),
        "config_sha256": sha256_file(config_path),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "physical_gpu_index": args.physical_gpu_index,
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "boundary": {
            "observable_inputs_only": True,
            "evaluator_labels_read": False,
            "agent_action_generated": False,
            "formal_agent_generation": False,
        },
    }
    try:
        if config.get("status") != "frozen_before_llm_judge_selection_outputs":
            raise RuntimeError("LLM Judge execution config is not frozen")
        if os.environ.get("CUDA_VISIBLE_DEVICES") != str(args.physical_gpu_index):
            raise RuntimeError("CUDA_VISIBLE_DEVICES must equal --physical-gpu-index")
        if payload["runner_sha256"] != str(config["runner"]["sha256"]):
            raise RuntimeError("LLM Judge runner hash differs from frozen config")
        e1_config_path = root_path(config["inputs"]["e1_selection_config"])
        preparation_path = root_path(config["inputs"]["preparation_manifest"])
        observable_path = root_path(config["inputs"]["observable_inputs"])
        judge_lock_path = root_path(config["judge"]["lock"])
        prompt_source_path = root_path(config["judge"]["prompt_source"])
        fixed_hashes = (
            (e1_config_path, config["inputs"]["e1_selection_config_sha256"]),
            (preparation_path, config["inputs"]["preparation_manifest_sha256"]),
            (observable_path, config["inputs"]["observable_inputs_sha256"]),
            (judge_lock_path, config["judge"]["lock_sha256"]),
            (prompt_source_path, config["judge"]["prompt_source_sha256"]),
        )
        for path, expected in fixed_hashes:
            if sha256_file(path) != str(expected):
                raise RuntimeError(f"frozen input hash mismatch: {path}")
        preparation = json.loads(preparation_path.read_text(encoding="utf-8"))
        if preparation["files"]["observable_inputs"]["sha256"] != str(
            config["inputs"]["observable_inputs_sha256"]
        ):
            raise RuntimeError("preparation manifest disagrees on observable input")
        observable = json.loads(observable_path.read_text(encoding="utf-8"))
        leaks = forbidden_key_paths(observable)
        if leaks:
            raise RuntimeError(f"forbidden keys present in model-visible input: {leaks[:3]}")
        memories = observable["memories"]
        targets = observable["targets"]
        if len(memories) != int(config["inputs"]["memory_count"]):
            raise RuntimeError("unexpected Judge memory count")
        if len(targets) != int(config["inputs"]["target_count"]):
            raise RuntimeError("unexpected Judge target count")
        memory_text_by_key = {
            str(item["memory_key"]): str(item["natural_text"]) for item in memories
        }
        if len(memory_text_by_key) != len(memories):
            raise RuntimeError("duplicate Judge memory keys")
        target_keys = [str(item["target_key"]) for item in targets]
        if len(target_keys) != len(set(target_keys)):
            raise RuntimeError("duplicate Judge target keys")
        for target in targets:
            candidate_keys = target["tfidf_top10_memory_keys"]
            if len(candidate_keys) != 10 or len(set(candidate_keys)) != 10:
                raise RuntimeError("Judge candidates must be ten unique memory keys")
            if not set(candidate_keys) <= set(memory_text_by_key):
                raise RuntimeError("Judge candidate references unknown memory")
            if set(target["judge_context"]) != REQUIRED_CONTEXT_KEYS:
                raise RuntimeError("Judge context differs from frozen prompt contract")

        model_path = Path(config["judge"]["remote_path"]).expanduser().resolve()
        model_manifest = root_path(config["judge"]["manifest"])
        if not model_path.is_dir() or not model_manifest.is_file():
            raise RuntimeError("Judge model or manifest is absent")
        if sha256_file(model_manifest) != str(config["judge"]["manifest_sha256"]):
            raise RuntimeError("Judge model-manifest hash mismatch")
        before = gpu_snapshot(args.physical_gpu_index)
        payload["gpu_before"] = before
        if before.get("returncode") != 0 or "memory_free_mib" not in before:
            raise RuntimeError("unable to query selected GPU")
        if int(before["memory_free_mib"]) < int(config["runtime"]["minimum_free_mib"]):
            payload["status"] = "blocked_insufficient_free_gpu_memory"
            payload["selection_passed"] = False
            write_json(output, payload)
            print(output)
            return 3
        verification = verify_sha256sum_manifest(model_path, model_manifest)
        payload["model_manifest_verification"] = verification
        if not verification["passed"]:
            raise RuntimeError("Judge model manifest verification failed")

        run_identity = canonical_sha256(
            {
                "config_sha256": payload["config_sha256"],
                "runner_sha256": payload["runner_sha256"],
                "observable_inputs_sha256": config["inputs"]["observable_inputs_sha256"],
                "judge_lock_sha256": config["judge"]["lock_sha256"],
                "model_manifest_sha256": config["judge"]["manifest_sha256"],
                "prompt_source_sha256": config["judge"]["prompt_source_sha256"],
            }
        )
        payload["run_identity_sha256"] = run_identity
        completed = load_checkpoint(checkpoint, run_identity)
        unknown_checkpoint_targets = set(completed) - set(target_keys)
        if unknown_checkpoint_targets:
            raise RuntimeError("checkpoint contains unknown target keys")
        payload["resume"] = {
            "checkpoint_path": str(checkpoint),
            "records_reused": len(completed),
        }

        import torch
        import transformers
        from transformers import AutoModelForCausalLM, AutoTokenizer

        if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
            raise RuntimeError("Judge runner must see exactly one CUDA GPU")
        if not torch.cuda.is_bf16_supported():
            raise RuntimeError("selected GPU does not support BF16")
        payload["runtime"] = {
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "cuda": torch.version.cuda,
            "dtype": "bfloat16",
        }
        seed = int(config["generation"]["seed"])
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        tokenizer = AutoTokenizer.from_pretrained(
            str(model_path), local_files_only=True, trust_remote_code=False
        )
        started = time.monotonic()
        model = AutoModelForCausalLM.from_pretrained(
            str(model_path),
            local_files_only=True,
            trust_remote_code=False,
            torch_dtype=torch.bfloat16,
            device_map={"": 0},
            low_cpu_mem_usage=True,
        )
        model.eval()
        payload["model_load_seconds"] = round(time.monotonic() - started, 3)
        pad_token_id = tokenizer.pad_token_id
        if pad_token_id is None:
            pad_token_id = tokenizer.eos_token_id
        max_new_tokens = int(config["generation"]["max_new_tokens"])
        max_input_tokens = int(config["generation"]["maximum_input_tokens"])
        progress_interval = int(config["runtime"]["progress_interval"])
        torch.cuda.reset_peak_memory_stats()
        run_started = time.monotonic()
        generated_this_run = 0

        for ordinal, target in enumerate(targets, start=1):
            target_key = str(target["target_key"])
            candidate_keys = [str(value) for value in target["tfidf_top10_memory_keys"]]
            candidates = tuple(
                JudgeCandidate(f"C{index:02d}", memory_text_by_key[memory_key])
                for index, memory_key in enumerate(candidate_keys, start=1)
            )
            messages = build_judge_messages(target["judge_context"], candidates)
            rendered = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
            rendered_hash = sha256_text(rendered)
            if target_key in completed:
                record = completed[target_key]
                if record.get("rendered_prompt_sha256") != rendered_hash:
                    raise RuntimeError(f"checkpoint prompt mismatch: {target_key}")
                if record.get("selected_memory_key") not in candidate_keys:
                    raise RuntimeError(f"checkpoint selection mismatch: {target_key}")
                continue
            inputs = tokenizer([rendered], return_tensors="pt")
            prompt_tokens = int(inputs["input_ids"].shape[1])
            if prompt_tokens > max_input_tokens:
                raise RuntimeError(f"Judge prompt exceeds frozen input limit: {target_key}")
            inputs = {key: value.to("cuda:0") for key, value in inputs.items()}
            generation_started = time.monotonic()
            with torch.inference_mode():
                generated = model.generate(
                    **inputs,
                    do_sample=False,
                    max_new_tokens=max_new_tokens,
                    pad_token_id=pad_token_id,
                )
            generation_seconds = time.monotonic() - generation_started
            new_tokens = generated[0][prompt_tokens:]
            raw_text = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
            decision = decide_with_rank1_fallback(raw_text, candidates)
            selected_index = int(decision.selected_candidate_id[1:]) - 1
            record = {
                "run_identity_sha256": run_identity,
                "target_key": target_key,
                "target_ordinal": ordinal,
                "selected_candidate_id": decision.selected_candidate_id,
                "selected_memory_key": candidate_keys[selected_index],
                "parse_succeeded": decision.parse_succeeded,
                "fallback_used": decision.fallback_used,
                "reason_code": decision.reason_code,
                "raw_response": raw_text,
                "rendered_prompt_sha256": rendered_hash,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": int(new_tokens.shape[0]),
                "generation_seconds": round(generation_seconds, 6),
            }
            append_checkpoint(checkpoint, record)
            completed[target_key] = record
            generated_this_run += 1
            if ordinal % progress_interval == 0 or ordinal == len(targets):
                print(
                    f"progress={ordinal}/{len(targets)} "
                    f"checkpoint_records={len(completed)} fallbacks="
                    f"{sum(bool(value['fallback_used']) for value in completed.values())}",
                    flush=True,
                )

        records = [completed[target_key] for target_key in target_keys]
        selected_counts = Counter(str(record["selected_memory_key"]) for record in records)
        checks = {
            "all_fifteen_model_files_verified": verification["checked"] == 15,
            "unique_record_per_target": len(records)
            == len({record["target_key"] for record in records})
            == len(targets),
            "all_selections_within_tfidf_top10": all(
                record["selected_memory_key"]
                in targets[index]["tfidf_top10_memory_keys"]
                for index, record in enumerate(records)
            ),
            "run_identity_uniform": all(
                record["run_identity_sha256"] == run_identity for record in records
            ),
            "prompt_hash_present": all(record["rendered_prompt_sha256"] for record in records),
        }
        payload.update(
            {
                "status": "passed" if all(checks.values()) else "failed_check",
                "selection_passed": all(checks.values()),
                "checks": checks,
                "counts": {
                    "targets": len(targets),
                    "records": len(records),
                    "generated_this_run": generated_this_run,
                    "reused_from_checkpoint": len(records) - generated_this_run,
                    "strict_parse_successes": sum(
                        bool(record["parse_succeeded"]) for record in records
                    ),
                    "fallbacks": sum(bool(record["fallback_used"]) for record in records),
                    "unique_selected_memories": len(selected_counts),
                },
                "timing": {
                    "current_process_selection_seconds": round(
                        time.monotonic() - run_started, 3
                    ),
                    "sum_generation_seconds_all_records": round(
                        sum(float(record["generation_seconds"]) for record in records), 3
                    ),
                },
                "token_usage": {
                    "prompt_tokens": sum(int(record["prompt_tokens"]) for record in records),
                    "completion_tokens": sum(
                        int(record["completion_tokens"]) for record in records
                    ),
                    "maximum_prompt_tokens": max(
                        int(record["prompt_tokens"]) for record in records
                    ),
                },
                "peak_cuda_memory_mib": round(
                    torch.cuda.max_memory_allocated() / 1024 / 1024, 2
                ),
                "checkpoint": {
                    "path": str(checkpoint),
                    "sha256": sha256_file(checkpoint),
                },
                "records": records,
            }
        )
    except Exception as error:
        payload["status"] = "error"
        payload["selection_passed"] = False
        payload["error"] = f"{type(error).__name__}: {error}"
        if checkpoint.is_file():
            payload["checkpoint"] = {
                "path": str(checkpoint),
                "sha256": sha256_file(checkpoint),
            }
    write_json(output, payload)
    print(output)
    return 0 if payload["selection_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
