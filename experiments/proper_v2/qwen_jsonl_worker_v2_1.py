from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping


DEFAULT_MODEL_PATH = Path(
    "/home/amax/PycharmProjects/AINegoProject/src/Models/LLM/Qwen3-8B"
)


def validate_request(value: Mapping[str, Any]) -> dict[str, Any]:
    request_id = str(value["request_id"])
    messages = value["messages"]
    if not isinstance(messages, list) or not messages:
        raise ValueError("messages must be a non-empty list")
    normalized = []
    for item in messages:
        if not isinstance(item, Mapping):
            raise ValueError("each message must be an object")
        role = str(item["role"])
        content = str(item["content"])
        if role not in {"system", "user", "assistant"}:
            raise ValueError(f"unsupported message role: {role}")
        normalized.append({"role": role, "content": content})
    return {
        "request_id": request_id,
        "messages": normalized,
        "seed": int(value["seed"]),
        "max_new_tokens": int(value.get("max_new_tokens", 256)),
    }


class QwenWorker:
    def __init__(self, model_path: Path) -> None:
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError(
                "Qwen worker requires torch, transformers, and accelerate"
            ) from exc
        if not model_path.is_dir():
            raise RuntimeError(f"local model path does not exist: {model_path}")
        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(
            str(model_path), local_files_only=True
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            str(model_path),
            device_map="auto",
            local_files_only=True,
            torch_dtype="auto",
        )
        self.model.eval()

    def complete(self, request: Mapping[str, Any]) -> str:
        seed = int(request["seed"])
        self.torch.manual_seed(seed)
        if self.torch.cuda.is_available():
            self.torch.cuda.manual_seed_all(seed)
        rendered = self.tokenizer.apply_chat_template(
            request["messages"],
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        inputs = self.tokenizer([rendered], return_tensors="pt")
        inputs = {
            key: value.to(self.model.device) for key, value in inputs.items()
        }
        with self.torch.inference_mode():
            generated = self.model.generate(
                **inputs,
                do_sample=False,
                max_new_tokens=int(request["max_new_tokens"]),
                pad_token_id=self.tokenizer.eos_token_id,
            )
        new_tokens = generated[0][inputs["input_ids"].shape[1] :]
        return self.tokenizer.decode(
            new_tokens, skip_special_tokens=True
        ).strip()


def response(
    request: Mapping[str, Any],
    *,
    raw_text: str,
    synthetic: bool,
) -> dict[str, Any]:
    return {
        "request_id": request["request_id"],
        "ok": True,
        "raw_text": raw_text,
        "synthetic_non_model_output": synthetic,
    }


def serve(*, model_path: Path, cpu_dry_run: bool) -> int:
    worker = None if cpu_dry_run else QwenWorker(model_path)
    for line in sys.stdin:
        if not line.strip():
            continue
        request_id = None
        try:
            raw = json.loads(line)
            if isinstance(raw, Mapping):
                request_id = raw.get("request_id")
            request = validate_request(raw)
            raw_text = (
                '{"kind":"stop","reason_code":"synthetic_cpu_dry_run"}'
                if cpu_dry_run
                else worker.complete(request)  # type: ignore[union-attr]
            )
            payload = response(
                request,
                raw_text=raw_text,
                synthetic=cpu_dry_run,
            )
        except Exception as exc:  # one bad request must not kill the worker
            payload = {
                "request_id": request_id,
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "synthetic_non_model_output": cpu_dry_run,
            }
        sys.stdout.write(
            json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n"
        )
        sys.stdout.flush()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Persistent local Qwen3 JSONL inference worker."
    )
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--cpu-dry-run", action="store_true")
    args = parser.parse_args()
    return serve(model_path=args.model_path, cpu_dry_run=args.cpu_dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
