from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from failure_memory.paper_2026.llm_judge import (  # noqa: E402
    PROMPT_VERSION,
    SYSTEM_MESSAGE,
    JudgeCandidate,
    build_judge_messages,
    decide_with_rank1_fallback,
)
from smoke_agent_model import (  # noqa: E402
    gpu_snapshot,
    sha256_file,
    verify_sha256sum_manifest,
    write_result,
)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def smoke_input() -> tuple[dict[str, Any], tuple[JudgeCandidate, ...]]:
    context = {
        "user_instruction": "Retrieve the requested public document.",
        "failed_tool_name": "get_document",
        "failed_arguments": {"document_id": "public-17"},
        "public_error_or_return": {
            "error_code": "timeout",
            "message": "The request timed out before completion.",
        },
        "remaining_retry_budget": {"retries_left": 1},
        "public_tool_schemas": [
            {
                "name": "get_document",
                "required": ["document_id"],
                "properties": {"document_id": {"type": "string"}},
            }
        ],
        "observable_history": [
            {
                "tool_name": "get_document",
                "arguments": {"document_id": "public-17"},
                "result": "timeout",
            }
        ],
    }
    candidates = (
        JudgeCandidate(
            "C01",
            "When a tool request times out before completion and one retry remains, retry the "
            "same action once with unchanged valid arguments.",
        ),
        JudgeCandidate(
            "C02",
            "After repeated authorization denials, stop and report that permission is required.",
        ),
        JudgeCandidate(
            "C03",
            "When a required argument is missing, add the missing field before retrying.",
        ),
    )
    return context, candidates


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Development-only exact-prompt smoke for the frozen Qwen LLM judge."
    )
    parser.add_argument("--model-path", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--physical-gpu-index", required=True, type=int)
    parser.add_argument("--minimum-free-mib", type=int, default=20000)
    parser.add_argument("--max-new-tokens", type=int, default=32)
    parser.add_argument("--seed", type=int, default=20260810)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    model_path = args.model_path.expanduser().resolve()
    manifest_path = args.manifest.expanduser().resolve()
    output = args.output.expanduser().resolve()
    prompt_source = ROOT / "src" / "failure_memory" / "paper_2026" / "llm_judge.py"
    payload: dict[str, Any] = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_kind": "paper_2026_llm_judge_prompt_smoke_not_formal_experiment",
        "model_path": str(model_path),
        "manifest_path": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path) if manifest_path.is_file() else None,
        "prompt_version": PROMPT_VERSION,
        "prompt_source_sha256": sha256_file(prompt_source),
        "system_message_sha256": sha256_text(SYSTEM_MESSAGE),
        "physical_gpu_index": args.physical_gpu_index,
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "generation": {
            "dtype": "bfloat16",
            "do_sample": False,
            "max_new_tokens": args.max_new_tokens,
            "thinking": "disabled",
            "seed": args.seed,
        },
    }
    try:
        if os.environ.get("CUDA_VISIBLE_DEVICES") != str(args.physical_gpu_index):
            raise RuntimeError("CUDA_VISIBLE_DEVICES must equal --physical-gpu-index")
        if not model_path.is_dir() or not manifest_path.is_file():
            raise RuntimeError("model path or manifest is absent")
        before = gpu_snapshot(args.physical_gpu_index)
        payload["gpu_before"] = before
        if before.get("returncode") != 0 or "memory_free_mib" not in before:
            raise RuntimeError("unable to query selected physical GPU")
        if int(before["memory_free_mib"]) < args.minimum_free_mib:
            payload["status"] = "blocked_insufficient_free_gpu_memory"
            payload["smoke_passed"] = False
            write_result(output, payload)
            print(output)
            return 3
        verification = verify_sha256sum_manifest(model_path, manifest_path)
        payload["model_manifest_verification"] = verification
        if not verification["passed"]:
            raise RuntimeError("Qwen manifest verification failed")

        import torch
        import transformers
        from transformers import AutoModelForCausalLM, AutoTokenizer

        if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
            raise RuntimeError("smoke process must see exactly one CUDA GPU")
        if not torch.cuda.is_bf16_supported():
            raise RuntimeError("selected GPU does not support BF16")
        payload["runtime"] = {
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "cuda": torch.version.cuda,
            "bf16_supported": torch.cuda.is_bf16_supported(),
        }
        context, candidates = smoke_input()
        messages = build_judge_messages(context, candidates)
        payload["synthetic_input_sha256"] = sha256_text(
            json.dumps(
                {"context": context, "candidates": [value.__dict__ for value in candidates]},
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        fallback_probe = decide_with_rank1_fallback("not-json", candidates)
        tokenizer = AutoTokenizer.from_pretrained(
            str(model_path), local_files_only=True, trust_remote_code=False
        )
        rendered = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        payload["rendered_prompt_sha256"] = sha256_text(rendered)

        torch.manual_seed(args.seed)
        torch.cuda.manual_seed_all(args.seed)
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
        inputs = tokenizer([rendered], return_tensors="pt")
        inputs = {key: value.to("cuda:0") for key, value in inputs.items()}
        prompt_tokens = int(inputs["input_ids"].shape[1])
        pad_token_id = tokenizer.pad_token_id
        if pad_token_id is None:
            pad_token_id = tokenizer.eos_token_id
        torch.cuda.reset_peak_memory_stats()
        started = time.monotonic()
        with torch.inference_mode():
            generated = model.generate(
                **inputs,
                do_sample=False,
                max_new_tokens=args.max_new_tokens,
                pad_token_id=pad_token_id,
            )
        payload["generation_seconds"] = round(time.monotonic() - started, 3)
        new_tokens = generated[0][prompt_tokens:]
        raw_text = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
        decision = decide_with_rank1_fallback(raw_text, candidates)
        payload["response"] = {
            "raw_text": raw_text,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": int(new_tokens.shape[0]),
            "peak_cuda_memory_mib": round(
                torch.cuda.max_memory_allocated() / 1024 / 1024, 2
            ),
            "decision": decision.to_mapping(),
        }
        payload["checks"] = {
            "all_manifest_files_verified": verification["checked"] == 15,
            "single_visible_gpu": torch.cuda.device_count() == 1,
            "bf16": next(model.parameters()).dtype == torch.bfloat16,
            "strict_json_parse": decision.parse_succeeded,
            "expected_candidate_c01": decision.selected_candidate_id == "C01",
            "no_fallback_for_valid_smoke": not decision.fallback_used,
            "invalid_output_fallback_is_c01": (
                fallback_probe.selected_candidate_id == "C01"
                and fallback_probe.fallback_used
                and not fallback_probe.parse_succeeded
            ),
        }
        payload["smoke_passed"] = all(payload["checks"].values())
        payload["status"] = "passed" if payload["smoke_passed"] else "failed_check"
    except Exception as error:
        payload["status"] = "error"
        payload["smoke_passed"] = False
        payload["error"] = f"{type(error).__name__}: {error}"
    write_result(output, payload)
    print(output)
    return 0 if payload["smoke_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
