from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SYSTEM_MESSAGE = (
    "You are a tool-using recovery agent. Return exactly one JSON object. "
    'Use either {"kind":"tool","tool_name":string,"args":object} '
    'or {"kind":"stop","reason_code":string}.'
)
SMOKE_USER_MESSAGE = (
    "Infrastructure smoke test only. Do not call a tool. "
    'Return exactly {"kind":"stop","reason_code":"smoke_ok"}.'
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def verify_sha256sum_manifest(model_dir: Path, manifest_path: Path) -> dict[str, Any]:
    checked = 0
    failures = []
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, separator, relative = line.partition("  ")
        if not separator or len(expected) != 64:
            failures.append({"entry": line, "reason": "invalid_manifest_line"})
            continue
        relative = relative[2:] if relative.startswith("./") else relative
        candidate = (model_dir / relative).resolve()
        try:
            candidate.relative_to(model_dir)
        except ValueError:
            failures.append({"entry": line, "reason": "path_escape"})
            continue
        checked += 1
        if not candidate.is_file():
            failures.append({"path": relative, "reason": "missing"})
        else:
            actual = sha256_file(candidate)
            if actual != expected:
                failures.append(
                    {"path": relative, "reason": "hash_mismatch", "actual": actual}
                )
    return {"kind": "sha256sum", "checked": checked, "failures": failures, "passed": not failures}


def verify_json_manifest(model_dir: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checked = 0
    failures = []
    for item in manifest.get("files", []):
        relative = str(item["relative_path"])
        candidate = (model_dir / relative).resolve()
        try:
            candidate.relative_to(model_dir)
        except ValueError:
            failures.append({"path": relative, "reason": "path_escape"})
            continue
        checked += 1
        if not candidate.is_file():
            failures.append({"path": relative, "reason": "missing"})
            continue
        if candidate.stat().st_size != int(item["bytes"]):
            failures.append({"path": relative, "reason": "size_mismatch"})
            continue
        actual = sha256_file(candidate)
        if actual != str(item["sha256"]):
            failures.append({"path": relative, "reason": "hash_mismatch", "actual": actual})
    return {
        "kind": "json",
        "manifest_repo_id": manifest.get("repo_id"),
        "manifest_revision": manifest.get("revision"),
        "checked": checked,
        "failures": failures,
        "passed": bool(checked) and not failures,
    }


def gpu_snapshot(physical_index: int) -> dict[str, Any]:
    completed = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=index,name,uuid,memory.total,memory.free,memory.used",
            "--format=csv,noheader,nounits",
            "-i",
            str(physical_index),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    record: dict[str, Any] = {
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }
    if completed.returncode == 0:
        fields = [value.strip() for value in completed.stdout.strip().split(",")]
        if len(fields) == 6:
            record.update(
                {
                    "physical_index": int(fields[0]),
                    "name": fields[1],
                    "uuid": fields[2],
                    "memory_total_mib": int(fields[3]),
                    "memory_free_mib": int(fields[4]),
                    "memory_used_mib": int(fields[5]),
                }
            )
    return record


def write_result(output: Path, payload: dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="One-model, one-process BF16 infrastructure smoke test.")
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--model-family", choices=("qwen3", "mistral"), required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-kind", choices=("sha256sum", "json"), required=True)
    parser.add_argument("--physical-gpu-index", type=int, required=True)
    parser.add_argument("--minimum-free-mib", type=int, default=40000)
    parser.add_argument("--max-new-tokens", type=int, default=64)
    parser.add_argument("--seed", type=int, default=20260809)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = args.output.expanduser().resolve()
    model_path = args.model_path.expanduser().resolve()
    manifest_path = args.manifest.expanduser().resolve()
    payload: dict[str, Any] = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_kind": "paper_2026_infrastructure_smoke_not_formal_experiment",
        "model_name": args.model_name,
        "model_family": args.model_family,
        "model_path": str(model_path),
        "manifest_path": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path) if manifest_path.is_file() else None,
        "generation": {
            "dtype": "bfloat16",
            "do_sample": False,
            "max_new_tokens": args.max_new_tokens,
            "seed": args.seed,
        },
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "physical_gpu_index": args.physical_gpu_index,
        "minimum_free_mib": args.minimum_free_mib,
        "checks": {},
    }
    try:
        if os.environ.get("CUDA_VISIBLE_DEVICES") != str(args.physical_gpu_index):
            raise RuntimeError("CUDA_VISIBLE_DEVICES must equal --physical-gpu-index")
        if not model_path.is_dir():
            raise RuntimeError(f"model directory does not exist: {model_path}")
        if not manifest_path.is_file():
            raise RuntimeError(f"manifest does not exist: {manifest_path}")
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

        verification = (
            verify_sha256sum_manifest(model_path, manifest_path)
            if args.manifest_kind == "sha256sum"
            else verify_json_manifest(model_path, manifest_path)
        )
        payload["model_manifest_verification"] = verification
        if not verification["passed"]:
            raise RuntimeError("model manifest verification failed")

        import torch
        import transformers
        from transformers import AutoModelForCausalLM, AutoTokenizer

        payload["runtime"] = {
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "cuda": torch.version.cuda,
            "bf16_supported": torch.cuda.is_bf16_supported(),
        }
        if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
            raise RuntimeError("smoke process must see exactly one CUDA GPU")
        if not torch.cuda.is_bf16_supported():
            raise RuntimeError("selected CUDA GPU does not support BF16")

        torch.manual_seed(args.seed)
        torch.cuda.manual_seed_all(args.seed)
        tokenizer = AutoTokenizer.from_pretrained(
            str(model_path), local_files_only=True, trust_remote_code=False
        )
        messages = [
            {"role": "system", "content": SYSTEM_MESSAGE},
            {"role": "user", "content": SMOKE_USER_MESSAGE},
        ]
        template_kwargs = {
            "tokenize": False,
            "add_generation_prompt": True,
        }
        if args.model_family == "qwen3":
            template_kwargs["enable_thinking"] = False
        rendered = tokenizer.apply_chat_template(messages, **template_kwargs)
        payload["rendered_prompt_sha256"] = sha256_text(rendered)

        load_started = time.monotonic()
        model = AutoModelForCausalLM.from_pretrained(
            str(model_path),
            local_files_only=True,
            trust_remote_code=False,
            torch_dtype=torch.bfloat16,
            device_map={"": 0},
            low_cpu_mem_usage=True,
        )
        model.eval()
        payload["model_load_seconds"] = round(time.monotonic() - load_started, 3)
        inputs = tokenizer([rendered], return_tensors="pt")
        inputs = {key: value.to("cuda:0") for key, value in inputs.items()}
        prompt_tokens = int(inputs["input_ids"].shape[1])
        pad_token_id = tokenizer.pad_token_id
        if pad_token_id is None:
            pad_token_id = tokenizer.eos_token_id
        torch.cuda.reset_peak_memory_stats()
        generation_started = time.monotonic()
        with torch.inference_mode():
            generated = model.generate(
                **inputs,
                do_sample=False,
                max_new_tokens=args.max_new_tokens,
                pad_token_id=pad_token_id,
            )
        payload["generation_seconds"] = round(time.monotonic() - generation_started, 3)
        new_tokens = generated[0][prompt_tokens:]
        raw_text = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
        payload["response"] = {
            "raw_text": raw_text,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": int(new_tokens.shape[0]),
            "peak_cuda_memory_mib": round(torch.cuda.max_memory_allocated() / 1024 / 1024, 2),
        }
        parsed = json.loads(raw_text)
        expected = {"kind": "stop", "reason_code": "smoke_ok"}
        payload["checks"] = {
            "strict_json": True,
            "expected_smoke_decision": parsed == expected,
            "single_visible_gpu": torch.cuda.device_count() == 1,
            "bf16": next(model.parameters()).dtype == torch.bfloat16,
        }
        payload["smoke_passed"] = all(payload["checks"].values())
        payload["status"] = "passed" if payload["smoke_passed"] else "failed_check"
    except Exception as exc:
        payload["status"] = "error"
        payload["smoke_passed"] = False
        payload["error"] = f"{type(exc).__name__}: {exc}"
    write_result(output, payload)
    print(output)
    return 0 if payload["smoke_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
