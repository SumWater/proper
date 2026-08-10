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


QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
QUERY = "A tool call timed out before completion and one bounded retry is available."
RELEVANT = "The tool timed out. I retried the original tool call once and it succeeded."
IRRELEVANT = "Authorization was persistently denied, so I stopped without another tool call."


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_manifest(model_dir: Path, manifest_path: Path) -> dict[str, Any]:
    """Verify a model snapshot while accepting Hugging Face cache symlinks.

    Snapshot entries are normally symlinks into the repository-level ``blobs``
    directory.  Reject lexical traversal first, then permit resolved targets only
    inside that model repository's cache directory.
    """
    checked = 0
    failures: list[dict[str, str]] = []
    model_dir = model_dir.resolve()
    repository_cache_dir = model_dir.parent.parent.resolve()
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, separator, relative = line.partition("  ")
        relative = relative.removeprefix("./")
        if not separator or len(expected) != 64:
            failures.append({"entry": line, "reason": "invalid_manifest_line"})
            continue
        relative_path = Path(relative)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            failures.append({"path": relative, "reason": "path_escape"})
            continue
        candidate = model_dir / relative_path
        checked += 1
        if not candidate.is_file():
            failures.append({"path": relative, "reason": "missing"})
            continue
        resolved_candidate = candidate.resolve()
        try:
            resolved_candidate.relative_to(repository_cache_dir)
        except ValueError:
            failures.append({"path": relative, "reason": "symlink_target_escape"})
            continue
        if sha256_file(resolved_candidate) != expected:
            failures.append({"path": relative, "reason": "hash_mismatch"})
    return {"checked": checked, "failures": failures, "passed": checked > 0 and not failures}


def gpu_snapshot(physical_index: int) -> dict[str, Any]:
    command = [
        "nvidia-smi",
        "--query-gpu=index,name,uuid,memory.total,memory.free,memory.used",
        "--format=csv,noheader,nounits",
        "-i",
        str(physical_index),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Direct-Transformers BGE dense encoder smoke.")
    parser.add_argument("--model-path", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--physical-gpu-index", required=True, type=int)
    parser.add_argument("--minimum-free-mib", type=int, default=8000)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    model_path = args.model_path.expanduser().resolve()
    manifest_path = args.manifest.expanduser().resolve()
    output = args.output.expanduser().resolve()
    payload: dict[str, Any] = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_kind": "paper_2026_dense_encoder_infrastructure_smoke",
        "model_path": str(model_path),
        "manifest_path": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path) if manifest_path.is_file() else None,
        "physical_gpu_index": args.physical_gpu_index,
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "encoding": {
            "dtype": "float32",
            "query_prefix": QUERY_PREFIX,
            "pooling": "first_token_cls",
            "normalize_embeddings": True,
            "max_length": 512,
        },
    }
    try:
        if os.environ.get("CUDA_VISIBLE_DEVICES") != str(args.physical_gpu_index):
            raise RuntimeError("CUDA_VISIBLE_DEVICES must equal --physical-gpu-index")
        if not model_path.is_dir() or not manifest_path.is_file():
            raise RuntimeError("model path or manifest is absent")
        before = gpu_snapshot(args.physical_gpu_index)
        payload["gpu_before"] = before
        if int(before.get("memory_free_mib", 0)) < args.minimum_free_mib:
            payload["status"] = "blocked_insufficient_free_gpu_memory"
            payload["smoke_passed"] = False
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            print(output)
            return 3
        verification = verify_manifest(model_path, manifest_path)
        payload["model_manifest_verification"] = verification
        if not verification["passed"]:
            raise RuntimeError("BGE manifest verification failed")

        import torch
        import torch.nn.functional as functional
        from transformers import AutoModel, AutoTokenizer

        if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
            raise RuntimeError("smoke process must see exactly one CUDA GPU")
        payload["runtime"] = {
            "torch": torch.__version__,
            "transformers": __import__("transformers").__version__,
            "cuda": torch.version.cuda,
        }
        tokenizer = AutoTokenizer.from_pretrained(
            str(model_path), local_files_only=True, trust_remote_code=False
        )
        started = time.monotonic()
        model = AutoModel.from_pretrained(
            str(model_path),
            local_files_only=True,
            trust_remote_code=False,
            torch_dtype=torch.float32,
        ).to("cuda:0")
        model.eval()
        payload["model_load_seconds"] = round(time.monotonic() - started, 3)
        texts = [QUERY_PREFIX + QUERY, RELEVANT, IRRELEVANT]
        batch = tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        )
        batch = {key: value.to("cuda:0") for key, value in batch.items()}
        torch.cuda.reset_peak_memory_stats()
        started = time.monotonic()
        with torch.inference_mode():
            hidden = model(**batch).last_hidden_state[:, 0]
            embeddings = functional.normalize(hidden, p=2, dim=1)
        payload["encoding_seconds"] = round(time.monotonic() - started, 3)
        scores = embeddings[0] @ embeddings[1:].T
        norms = embeddings.norm(p=2, dim=1)
        payload["result"] = {
            "shape": list(embeddings.shape),
            "norms": [round(float(value), 8) for value in norms.cpu()],
            "relevant_score": round(float(scores[0].cpu()), 8),
            "irrelevant_score": round(float(scores[1].cpu()), 8),
            "peak_cuda_memory_mib": round(
                torch.cuda.max_memory_allocated() / 1024 / 1024, 2
            ),
        }
        payload["checks"] = {
            "manifest_six_files": verification["checked"] == 6,
            "single_visible_gpu": torch.cuda.device_count() == 1,
            "embedding_shape_3_by_1024": list(embeddings.shape) == [3, 1024],
            "unit_norm": all(abs(float(value) - 1.0) < 1e-5 for value in norms),
            "relevant_above_irrelevant": float(scores[0]) > float(scores[1]),
            "float32": embeddings.dtype == torch.float32,
        }
        payload["smoke_passed"] = all(payload["checks"].values())
        payload["status"] = "passed" if payload["smoke_passed"] else "failed_check"
    except Exception as error:
        payload["status"] = "error"
        payload["smoke_passed"] = False
        payload["error"] = f"{type(error).__name__}: {error}"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)
    return 0 if payload["smoke_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
