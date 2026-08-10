from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Mapping

import yaml


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs" / "paper_2026" / "agent_generation_v1_0.yaml"
sys.path.insert(0, str(ROOT))

from experiments.proper_v1.agent_runtime import (  # noqa: E402
    canonical,
    decision_payload,
    parse_decision,
    sha256_text,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def root_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_model_files(
    *,
    model_path: Path,
    manifest_path: Path,
    manifest_format: str,
) -> dict[str, Any]:
    entries: list[tuple[str, str, int | None]] = []
    if manifest_format == "sha256sum":
        for line in manifest_path.read_text(encoding="utf-8").splitlines():
            expected, separator, relative = line.partition("  ")
            if not separator or len(expected) != 64:
                raise RuntimeError(f"invalid model-manifest line: {line!r}")
            entries.append((relative.removeprefix("./"), expected, None))
    elif manifest_format == "json_files":
        payload = read_json(manifest_path)
        entries = [
            (item["relative_path"], item["sha256"], int(item["bytes"]))
            for item in payload["files"]
        ]
    else:
        raise RuntimeError(f"unsupported model manifest format: {manifest_format}")
    total_bytes = 0
    resolved_root = model_path.resolve()
    for relative, expected, expected_bytes in entries:
        candidate = (model_path / relative).resolve()
        try:
            candidate.relative_to(resolved_root)
        except ValueError as exc:
            raise RuntimeError(f"model manifest path escapes model directory: {relative}") from exc
        if not candidate.is_file():
            raise RuntimeError(f"model file missing: {candidate}")
        size = candidate.stat().st_size
        if expected_bytes is not None and size != expected_bytes:
            raise RuntimeError(f"model file size mismatch: {candidate}")
        if sha256_file(candidate) != expected:
            raise RuntimeError(f"model file hash mismatch: {candidate}")
        total_bytes += size
    return {"checked_file_count": len(entries), "checked_total_bytes": total_bytes}


def verify_frozen(config: Mapping[str, Any]) -> dict[str, str]:
    if config.get("status") != "frozen_before_formal_agent_generation":
        raise RuntimeError("agent-generation config is not frozen")
    runner_hash = sha256_file(Path(__file__).resolve())
    if runner_hash != str(config["runner"]["sha256"]):
        raise RuntimeError("agent-generation runner hash differs from frozen config")
    verified: dict[str, str] = {}
    for name, entry in config["inputs"].items():
        path = root_path(entry["path"])
        if not path.is_file():
            raise RuntimeError(f"missing frozen input: {name}: {path}")
        actual = sha256_file(path)
        if actual != str(entry["sha256"]):
            raise RuntimeError(f"frozen input hash mismatch: {name}: {actual}")
        verified[str(name)] = actual
    return verified


def load_plan(config: Mapping[str, Any], model_name: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    prompt_manifest = read_json(root_path(config["inputs"]["prompt_manifest"]["path"]))
    planned_calls = read_json(root_path(config["inputs"]["planned_calls"]["path"]))
    prompt_by_hash = {
        item["prompt_sha256"]: item for item in prompt_manifest["unique_prompts"]
    }
    hashes = planned_calls["models"][model_name]["new_prompt_sha256"]
    if len(hashes) != planned_calls["models"][model_name]["new_call_count"]:
        raise RuntimeError("planned call count/list mismatch")
    if len(hashes) != len(set(hashes)) or hashes != sorted(hashes):
        raise RuntimeError("planned prompt hashes must be unique and sorted")
    missing = [value for value in hashes if value not in prompt_by_hash]
    if missing:
        raise RuntimeError(f"planned prompt absent from manifest: {missing[0]}")
    requests = [prompt_by_hash[value] for value in hashes]
    for item in requests:
        if sha256_text(item["prompt"]) != item["prompt_sha256"]:
            raise RuntimeError(f"raw prompt hash mismatch: {item['prompt_sha256']}")
        if sha256_text(canonical(item["messages"])) != item["messages_sha256"]:
            raise RuntimeError(f"message hash mismatch: {item['prompt_sha256']}")
    return requests, planned_calls


def validate_checkpoint_record(
    record: Mapping[str, Any],
    *,
    model_name: str,
    model_manifest_sha256: str,
    generation: Mapping[str, Any],
    request: Mapping[str, Any],
) -> None:
    if record.get("status") != "formal_model_output":
        raise RuntimeError("checkpoint contains a non-formal row")
    if record.get("synthetic_non_model_output") is not False:
        raise RuntimeError("checkpoint contains a synthetic row")
    if record.get("model_name") != model_name:
        raise RuntimeError("checkpoint model name mismatch")
    if record.get("model_manifest_sha256") != model_manifest_sha256:
        raise RuntimeError("checkpoint model manifest mismatch")
    if record.get("generation") != generation:
        raise RuntimeError("checkpoint generation policy mismatch")
    if record.get("prompt_sha256") != request["prompt_sha256"]:
        raise RuntimeError("checkpoint prompt identity mismatch")
    if record.get("messages_sha256") != request["messages_sha256"]:
        raise RuntimeError("checkpoint message identity mismatch")
    if sha256_text(str(record["raw_model_output"])) != record["raw_model_output_sha256"]:
        raise RuntimeError("checkpoint model-output hash mismatch")
    decision, parse_valid, parse_error = parse_decision(str(record["raw_model_output"]))
    if record.get("decision") != decision_payload(decision):
        raise RuntimeError("checkpoint parsed decision mismatch")
    if record.get("parse_valid") != parse_valid or record.get("parse_error") != parse_error:
        raise RuntimeError("checkpoint parse metadata mismatch")


def load_checkpoint(
    path: Path,
    *,
    request_by_hash: Mapping[str, Mapping[str, Any]],
    model_name: str,
    model_manifest_sha256: str,
    generation: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return records
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        record = json.loads(line)
        prompt_hash = str(record.get("prompt_sha256"))
        request = request_by_hash.get(prompt_hash)
        if request is None:
            raise RuntimeError(f"checkpoint row {line_number} is outside frozen plan")
        validate_checkpoint_record(
            record,
            model_name=model_name,
            model_manifest_sha256=model_manifest_sha256,
            generation=generation,
            request=request,
        )
        if prompt_hash in records and records[prompt_hash] != record:
            raise RuntimeError(f"conflicting duplicate checkpoint row: {prompt_hash}")
        records[prompt_hash] = record
    return records


class TransformersAgentModel:
    def __init__(self, *, model_path: Path, family: str) -> None:
        try:
            import torch
            import transformers
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError("formal generation requires torch, transformers, and accelerate") from exc
        if not model_path.is_dir():
            raise RuntimeError(f"local model directory does not exist: {model_path}")
        self.torch = torch
        self.transformers_version = transformers.__version__
        self.family = family
        self.tokenizer = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            str(model_path),
            device_map="auto",
            local_files_only=True,
            torch_dtype="auto",
            trust_remote_code=False,
        )
        self.model.eval()

    def complete(self, messages: list[dict[str, str]], generation: Mapping[str, Any]) -> dict[str, Any]:
        seed = int(generation["seed"])
        self.torch.manual_seed(seed)
        if self.torch.cuda.is_available():
            self.torch.cuda.manual_seed_all(seed)
        template_kwargs: dict[str, Any] = {
            "tokenize": False,
            "add_generation_prompt": True,
        }
        if self.family == "qwen3":
            template_kwargs["enable_thinking"] = False
        rendered = self.tokenizer.apply_chat_template(messages, **template_kwargs)
        inputs = self.tokenizer([rendered], return_tensors="pt")
        inputs = {key: value.to(self.model.device) for key, value in inputs.items()}
        prompt_tokens = int(inputs["input_ids"].shape[1])
        started = time.perf_counter()
        with self.torch.inference_mode():
            generated = self.model.generate(
                **inputs,
                do_sample=False,
                max_new_tokens=int(generation["max_new_tokens"]),
                pad_token_id=self.tokenizer.eos_token_id,
            )
        elapsed = time.perf_counter() - started
        new_tokens = generated[0][prompt_tokens:]
        raw = self.tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
        return {
            "raw_model_output": raw,
            "rendered_prompt_sha256": sha256_text(rendered),
            "prompt_token_count": prompt_tokens,
            "completion_token_count": int(new_tokens.shape[0]),
            "generation_seconds": elapsed,
        }


def append_checkpoint(path: Path, record: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Frozen E2/E3 unique-prompt agent generation.")
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--model", choices=("qwen3_8b", "mistral_7b_instruct_v0_3"), required=True)
    parser.add_argument("--model-path", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    verified = verify_frozen(config)
    requests, planned_calls = load_plan(config, args.model)
    model_config = config["models"][args.model]
    expected_count = int(model_config["expected_new_calls"])
    if len(requests) != expected_count:
        raise RuntimeError("frozen model call count differs from prompt plan")
    generation = dict(config["generation"])
    checkpoint_path = root_path(model_config["checkpoint"])
    result_path = root_path(model_config["result"])
    request_by_hash = {item["prompt_sha256"]: item for item in requests}
    completed = load_checkpoint(
        checkpoint_path,
        request_by_hash=request_by_hash,
        model_name=args.model,
        model_manifest_sha256=model_config["manifest_sha256"],
        generation=generation,
    )
    if args.validate_only:
        print(
            json.dumps(
                {
                    "status": "validated_no_model_loaded_no_output_written",
                    "model": args.model,
                    "expected_new_calls": expected_count,
                    "checkpoint_completed": len(completed),
                    "remaining": expected_count - len(completed),
                    "verified_inputs": verified,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0

    pending = [item for item in requests if item["prompt_sha256"] not in completed]
    if args.limit is not None:
        if args.limit < 1:
            raise ValueError("--limit must be positive")
        pending = pending[: args.limit]
    model_path = args.model_path or Path(model_config["remote_path"])
    model_file_verification = verify_model_files(
        model_path=model_path,
        manifest_path=root_path(config["inputs"][model_config["manifest_input"]]["path"]),
        manifest_format=model_config["manifest_format"],
    )
    print(
        f"{args.model}: verified {model_file_verification['checked_file_count']} model files",
        flush=True,
    )
    worker = TransformersAgentModel(model_path=model_path, family=model_config["family"])
    started = time.perf_counter()
    initial_completed = len(completed)
    for index, request in enumerate(pending, 1):
        completion = worker.complete(request["messages"], generation)
        decision, parse_valid, parse_error = parse_decision(completion["raw_model_output"])
        record = {
            "schema_version": 1,
            "status": "formal_model_output",
            "synthetic_non_model_output": False,
            "model_name": args.model,
            "model_manifest_sha256": model_config["manifest_sha256"],
            "generation": generation,
            "prompt_sha256": request["prompt_sha256"],
            "messages_sha256": request["messages_sha256"],
            "rendered_prompt_sha256": completion["rendered_prompt_sha256"],
            "raw_model_output": completion["raw_model_output"],
            "raw_model_output_sha256": sha256_text(completion["raw_model_output"]),
            "decision": decision_payload(decision),
            "parse_valid": parse_valid,
            "parse_error": parse_error,
            "usage": {
                "prompt_token_count": completion["prompt_token_count"],
                "completion_token_count": completion["completion_token_count"],
            },
            "generation_seconds": completion["generation_seconds"],
        }
        validate_checkpoint_record(
            record,
            model_name=args.model,
            model_manifest_sha256=model_config["manifest_sha256"],
            generation=generation,
            request=request,
        )
        append_checkpoint(checkpoint_path, record)
        completed[request["prompt_sha256"]] = record
        if index == 1 or index % int(config["progress_every"]) == 0 or index == len(pending):
            elapsed = max(time.perf_counter() - started, 1e-9)
            print(
                f"{args.model}: generated={index}/{len(pending)} "
                f"total={len(completed)}/{expected_count} speed={index / elapsed:.3f} prompts/s",
                flush=True,
            )

    if len(completed) == expected_count:
        records = [completed[key] for key in sorted(completed)]
        result = {
            "schema_version": 1,
            "stage_id": "e2_e3_agent_generation",
            "status": "complete",
            "model_name": args.model,
            "model_manifest_sha256": model_config["manifest_sha256"],
            "generation": generation,
            "expected_count": expected_count,
            "record_count": len(records),
            "parse_failure_count": sum(not item["parse_valid"] for item in records),
            "checkpoint_sha256": sha256_file(checkpoint_path),
            "input_identities": verified,
            "runtime": {
                "python": sys.version,
                "torch": worker.torch.__version__,
                "transformers": worker.transformers_version,
                "cuda": worker.torch.version.cuda,
                "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
                "device_name": (
                    worker.torch.cuda.get_device_name(0)
                    if worker.torch.cuda.is_available()
                    else None
                ),
                "model_dtype": str(next(worker.model.parameters()).dtype),
                "model_file_verification": model_file_verification,
                "peak_cuda_memory_mib": (
                    worker.torch.cuda.max_memory_allocated() / 1024 / 1024
                    if worker.torch.cuda.is_available()
                    else 0.0
                ),
            },
            "records": records,
        }
        write_json_atomic(result_path, result)
        print(f"complete: {result_path}", flush=True)
    else:
        print(
            f"partial checkpoint: initial={initial_completed} now={len(completed)} "
            f"remaining={expected_count - len(completed)}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
