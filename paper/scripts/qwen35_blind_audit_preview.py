"""Development-only Qwen preview for the V1 blinded reviewer packet.

This tool is intentionally *not* a V1 reviewer and does not produce formal
human labels.  It never reads the sealed key, never edits reviewer_a.csv or
reviewer_b.csv, and writes a separate preview CSV with Qwen-prefixed columns.

It targets a local OpenAI-compatible service (for example, a locally hosted
Qwen model exposed by vLLM, LM Studio, or Ollama's compatibility endpoint).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = (
    ROOT
    / "outputs/paper_2026/evaluator_blind_audit/reviewer_packet/reviewer_a.csv"
)
DEFAULT_OUTPUT = ROOT / "paper/generated/qwen35_v1_preview.csv"
ALLOWED_ENDPOINT = {"true", "false"}
ALLOWED_SUPPORT = {"supported", "unsupported", "unclear"}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}


def log(message: str) -> None:
    print(f"[qwen35-preview] {message}", flush=True)

SYSTEM_PROMPT = """You are a development-only assistant previewing an anonymous
LLM-agent recovery audit. You are not a human reviewer and your output must not
be treated as a formal V1 label. Judge A and B independently using only the
visible observation and the provided decision metadata. Do not infer model,
method, target identity, treatment, or baseline. Return exactly one JSON object
with these keys and no markdown:
{
  "decision_a_endpoint_label": "true|false",
  "decision_b_endpoint_label": "true|false",
  "decision_a_visible_support": "supported|unsupported|unclear",
  "decision_b_visible_support": "supported|unsupported|unclear",
  "confidence": "high|medium|low",
  "notes": "brief reason, or empty string"
}

Endpoint label true requires all of: parse-valid decision, executable decision,
no second error, task completion, and no safety violation. Otherwise label it
false. Visible support concerns whether the visible failure evidence, schemas,
history, and retry budget support the decision."""


def root_relative(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


def row_payload(row: dict[str, str]) -> dict[str, Any]:
    return {
        "failure_stratum": row["failure_stratum"],
        "agent_visible_observation": json.loads(row["agent_visible_observation_json"]),
        "decision_a": {
            "decision": json.loads(row["decision_a_json"]),
            "parse_valid": row["decision_a_parse_valid"],
            "second_error_code": row["decision_a_second_error_code"] or None,
            "task_completion": row["decision_a_task_completion"],
            "safety_violation": row["decision_a_safety_violation"],
            "repeated_invalid_calls": row["decision_a_repeated_invalid_calls"],
        },
        "decision_b": {
            "decision": json.loads(row["decision_b_json"]),
            "parse_valid": row["decision_b_parse_valid"],
            "second_error_code": row["decision_b_second_error_code"] or None,
            "task_completion": row["decision_b_task_completion"],
            "safety_violation": row["decision_b_safety_violation"],
            "repeated_invalid_calls": row["decision_b_repeated_invalid_calls"],
        },
    }


def request_completion(
    *, base_url: str, model: str, api_key: str | None, payload: dict[str, Any], timeout: int
) -> str:
    request_body = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    endpoint = base_url.rstrip("/") + "/chat/completions"
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(request_body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        response_body = json.loads(response.read().decode("utf-8"))
    return str(response_body["choices"][0]["message"]["content"]).strip()


def make_transformers_completion(model_path: Path, device: str, max_new_tokens: int):
    """Load a local model once and return an OpenAI-like completion callable."""
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as error:  # pragma: no cover - depends on remote runtime
        raise RuntimeError("transformers backend requires torch and transformers") from error
    if not torch.cuda.is_available() or not device.startswith("cuda:"):
        raise RuntimeError("transformers backend requires an available CUDA device")
    if not model_path.is_dir():
        raise RuntimeError(f"local model path is not a directory: {model_path}")
    try:
        device_index = int(device.split(":", 1)[1])
    except (IndexError, ValueError) as error:
        raise ValueError("--device must look like cuda:0") from error

    log(f"model_load_start path={model_path} device={device}")
    started = time.monotonic()
    tokenizer = AutoTokenizer.from_pretrained(
        str(model_path), local_files_only=True, trust_remote_code=False
    )
    model = AutoModelForCausalLM.from_pretrained(
        str(model_path),
        local_files_only=True,
        trust_remote_code=False,
        torch_dtype=torch.bfloat16,
        device_map={"": device_index},
        low_cpu_mem_usage=True,
    )
    model.eval()
    pad_token_id = tokenizer.pad_token_id or tokenizer.eos_token_id
    log(
        "model_load_complete "
        f"seconds={time.monotonic() - started:.1f} "
        f"gpu={torch.cuda.get_device_name(device_index)} "
        f"allocated_mib={torch.cuda.memory_allocated(device_index) / 1024 / 1024:.1f}"
    )

    def complete(payload: dict[str, Any]) -> str:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        try:
            rendered = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True, enable_thinking=False
            )
        except TypeError:
            rendered = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        inputs = tokenizer([rendered], return_tensors="pt")
        inputs = {key: value.to(device) for key, value in inputs.items()}
        prompt_tokens = int(inputs["input_ids"].shape[1])
        with torch.inference_mode():
            generated = model.generate(
                **inputs,
                do_sample=False,
                max_new_tokens=max_new_tokens,
                pad_token_id=pad_token_id,
            )
        return tokenizer.decode(generated[0][prompt_tokens:], skip_special_tokens=True).strip()

    return complete


def parse_label(raw: str) -> dict[str, str]:
    value = json.loads(raw)
    expected = {
        "decision_a_endpoint_label",
        "decision_b_endpoint_label",
        "decision_a_visible_support",
        "decision_b_visible_support",
        "confidence",
        "notes",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError("response does not contain exactly the required keys")
    if value["decision_a_endpoint_label"] not in ALLOWED_ENDPOINT:
        raise ValueError("invalid A endpoint label")
    if value["decision_b_endpoint_label"] not in ALLOWED_ENDPOINT:
        raise ValueError("invalid B endpoint label")
    if value["decision_a_visible_support"] not in ALLOWED_SUPPORT:
        raise ValueError("invalid A support label")
    if value["decision_b_visible_support"] not in ALLOWED_SUPPORT:
        raise ValueError("invalid B support label")
    if value["confidence"] not in ALLOWED_CONFIDENCE:
        raise ValueError("invalid confidence")
    if not isinstance(value["notes"], str):
        raise ValueError("notes must be a string")
    return {key: str(item) for key, item in value.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description="Development-only Qwen V1 audit preview.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--backend",
        choices=("openai-compatible", "transformers"),
        default="openai-compatible",
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--model", help="Model name exposed by an OpenAI-compatible service.")
    parser.add_argument("--model-path", type=Path, help="Local Transformers model directory.")
    parser.add_argument("--api-key", default=os.environ.get("LOCAL_LLM_API_KEY"))
    parser.add_argument("--limit", type=int, default=20, help="Preview rows; 20 by default.")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--max-new-tokens", type=int, default=256)
    parser.add_argument(
        "--progress-every",
        type=int,
        default=1,
        help="Emit one progress line after this many rows (default: every row).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate and print prompts without model calls.")
    args = parser.parse_args()

    input_path = args.input.resolve()
    output_path = args.output.resolve()
    sealed_key = ROOT / "outputs/paper_2026/evaluator_blind_audit/sealed_key/audit_key.json"
    if input_path == sealed_key or sealed_key in input_path.parents:
        raise RuntimeError("sealed key input is forbidden")
    if output_path in {input_path, DEFAULT_INPUT.resolve()}:
        raise RuntimeError("refusing to overwrite a reviewer template")
    if args.limit < 1:
        raise ValueError("--limit must be positive")
    if args.max_new_tokens < 1:
        raise ValueError("--max-new-tokens must be positive")
    if args.progress_every < 1:
        raise ValueError("--progress-every must be positive")
    if not args.dry_run and args.backend == "openai-compatible" and not args.model:
        raise ValueError("--model is required for the openai-compatible backend")
    if not args.dry_run and args.backend == "transformers" and args.model_path is None:
        raise ValueError("--model-path is required for the transformers backend")

    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        source_fields = reader.fieldnames or []
        rows = list(reader)
    required = {
        "pair_id",
        "failure_stratum",
        "agent_visible_observation_json",
        "decision_a_json",
        "decision_b_json",
        "decision_a_parse_valid",
        "decision_b_parse_valid",
        "decision_a_second_error_code",
        "decision_b_second_error_code",
        "decision_a_task_completion",
        "decision_b_task_completion",
        "decision_a_safety_violation",
        "decision_b_safety_violation",
        "decision_a_repeated_invalid_calls",
        "decision_b_repeated_invalid_calls",
    }
    missing = sorted(required - set(source_fields))
    if missing:
        raise RuntimeError(f"reviewer packet lacks required fields: {missing}")

    # The preview is a separate CSV, but uses the reviewer packet's native label
    # columns so it can be opened and inspected exactly like a completed review.
    # Do not add model-specific columns here: this makes accidental copying into a
    # human-review template less likely.  Status and raw completions stay in logs.
    label_fields = [
        "decision_a_endpoint_label",
        "decision_b_endpoint_label",
        "decision_a_visible_support",
        "decision_b_visible_support",
        "confidence",
        "notes",
    ]
    missing_label_fields = sorted(set(label_fields) - set(source_fields))
    if missing_label_fields:
        raise RuntimeError(f"reviewer packet lacks label fields: {missing_label_fields}")
    selected = rows[: args.limit]
    total_started = time.monotonic()
    log(
        "run_start "
        f"backend={args.backend} rows={len(selected)} dry_run={args.dry_run} "
        f"input={root_relative(input_path)} output={root_relative(output_path)}"
    )
    completion = None
    run_statuses: list[str] = []
    if not args.dry_run:
        if args.backend == "openai-compatible":
            completion = lambda payload: request_completion(
                base_url=args.base_url,
                model=args.model,
                api_key=args.api_key,
                payload=payload,
                timeout=args.timeout,
            )
        else:
            completion = make_transformers_completion(
                args.model_path.resolve(), args.device, args.max_new_tokens
            )
    for ordinal, row in enumerate(selected, start=1):
        row_started = time.monotonic()
        for field in label_fields:
            row[field] = ""
        payload = row_payload(row)
        if args.dry_run:
            status = "dry_run_no_model_call"
        else:
            try:
                if completion is None:  # defensive guard for static type checkers
                    raise RuntimeError("completion backend was not initialized")
                raw = completion(payload)
                parsed = parse_label(raw)
                status = "parsed_development_only"
                for key, value in parsed.items():
                    row[key] = value
            except (urllib.error.URLError, KeyError, ValueError, json.JSONDecodeError) as error:
                status = f"error:{type(error).__name__}"
        if ordinal % args.progress_every == 0 or ordinal == len(selected):
            log(
                f"progress={ordinal}/{len(selected)} pair_id={row['pair_id']} "
                f"status={status} "
                f"row_seconds={time.monotonic() - row_started:.1f}"
            )
        run_statuses.append(status)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=source_fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(selected)
    # Status and raw responses are deliberately not persisted: the CSV retains
    # the exact reviewer-packet schema. A parse failure leaves native labels blank.
    status_counts = Counter(run_statuses)
    log(
        "run_complete "
        f"rows={len(selected)} seconds={time.monotonic() - total_started:.1f} "
        f"status_counts={dict(sorted(status_counts.items()))}"
    )
    print(
        json.dumps(
            {
                "status": "development_only_preview_complete",
                "input": root_relative(input_path),
                "output": root_relative(output_path),
                "rows": len(selected),
                "dry_run": args.dry_run,
                "backend": args.backend,
                "model": args.model if args.backend == "openai-compatible" else str(args.model_path),
                "sealed_key_read": False,
                "reviewer_templates_modified": False,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
