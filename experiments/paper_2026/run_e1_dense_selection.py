from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

import yaml


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "paper_2026"))

from smoke_dense_encoder import gpu_snapshot, verify_manifest  # noqa: E402


CONFIG = ROOT / "configs" / "paper_2026" / "e1_dense_execution_v1_0.yaml"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def root_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def write_result(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def batches(values: Sequence[str], size: int) -> Sequence[Sequence[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Frozen E1 BGE Dense Rank-1 selection runner.")
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--physical-gpu-index", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = args.config.expanduser().resolve()
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    output = root_path(config["output"])
    payload: dict[str, Any] = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_kind": "paper_2026_e1_formal_offline_dense_selection",
        "status": "initializing",
        "config_path": str(config_path),
        "config_sha256": sha256_file(config_path),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "physical_gpu_index": args.physical_gpu_index,
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "boundary": {
            "evaluator_labels_read": False,
            "agent_model_loaded": False,
            "formal_agent_generation": False,
        },
    }
    try:
        if config.get("status") != "frozen_before_dense_selection_outputs":
            raise RuntimeError("Dense execution config is not frozen")
        if os.environ.get("CUDA_VISIBLE_DEVICES") != str(args.physical_gpu_index):
            raise RuntimeError("CUDA_VISIBLE_DEVICES must equal --physical-gpu-index")
        expected_runner = str(config["runner"]["sha256"])
        if payload["runner_sha256"] != expected_runner:
            raise RuntimeError("Dense runner hash differs from frozen config")
        e1_config_path = root_path(config["inputs"]["e1_selection_config"])
        if sha256_file(e1_config_path) != str(
            config["inputs"]["e1_selection_config_sha256"]
        ):
            raise RuntimeError("E1 selection-config hash mismatch")
        dense_lock_path = root_path(config["model"]["lock"])
        if sha256_file(dense_lock_path) != str(config["model"]["lock_sha256"]):
            raise RuntimeError("Dense result-lock hash mismatch")
        preparation_path = root_path(config["inputs"]["preparation_manifest"])
        observable_path = root_path(config["inputs"]["observable_inputs"])
        if sha256_file(preparation_path) != str(
            config["inputs"]["preparation_manifest_sha256"]
        ):
            raise RuntimeError("E1 preparation-manifest hash mismatch")
        if sha256_file(observable_path) != str(config["inputs"]["observable_inputs_sha256"]):
            raise RuntimeError("E1 observable-input hash mismatch")
        preparation = json.loads(preparation_path.read_text(encoding="utf-8"))
        if (
            preparation["files"]["observable_inputs"]["sha256"]
            != str(config["inputs"]["observable_inputs_sha256"])
        ):
            raise RuntimeError("preparation manifest disagrees on observable input")
        observable = json.loads(observable_path.read_text(encoding="utf-8"))
        memories = observable["memories"]
        targets = observable["targets"]
        if len(memories) != int(config["inputs"]["memory_count"]):
            raise RuntimeError("unexpected Dense memory count")
        if len(targets) != int(config["inputs"]["target_count"]):
            raise RuntimeError("unexpected Dense target count")
        memory_keys = [str(item["memory_key"]) for item in memories]
        target_keys = [str(item["target_key"]) for item in targets]
        if memory_keys != sorted(memory_keys) or len(memory_keys) != len(set(memory_keys)):
            raise RuntimeError("memory keys must be unique and lexically ordered")
        if len(target_keys) != len(set(target_keys)):
            raise RuntimeError("target keys must be unique")

        model_path = Path(config["model"]["remote_path"]).expanduser().resolve()
        model_manifest = root_path(config["model"]["manifest"])
        if not model_path.is_dir() or not model_manifest.is_file():
            raise RuntimeError("Dense model or manifest is absent")
        if sha256_file(model_manifest) != str(config["model"]["manifest_sha256"]):
            raise RuntimeError("Dense model-manifest identity mismatch")
        before = gpu_snapshot(args.physical_gpu_index)
        payload["gpu_before"] = before
        if before.get("returncode") != 0 or "memory_free_mib" not in before:
            raise RuntimeError("unable to query selected GPU")
        if int(before["memory_free_mib"]) < int(config["runtime"]["minimum_free_mib"]):
            payload["status"] = "blocked_insufficient_free_gpu_memory"
            payload["selection_passed"] = False
            write_result(output, payload)
            print(output)
            return 3
        verification = verify_manifest(model_path, model_manifest)
        payload["model_manifest_verification"] = verification
        if not verification["passed"]:
            raise RuntimeError("Dense model manifest verification failed")

        import torch
        import torch.nn.functional as functional
        import transformers
        from transformers import AutoModel, AutoTokenizer

        if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
            raise RuntimeError("Dense runner must see exactly one CUDA GPU")
        payload["runtime"] = {
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "cuda": torch.version.cuda,
            "dtype": "float32",
            "batch_size": int(config["encoding"]["batch_size"]),
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
        batch_size = int(config["encoding"]["batch_size"])
        max_length = int(config["encoding"]["max_length"])

        def encode(texts: Sequence[str], transform: Callable[[str], str]) -> Any:
            encoded_batches = []
            for text_batch in batches(list(texts), batch_size):
                transformed = [transform(value) for value in text_batch]
                tokens = tokenizer(
                    transformed,
                    padding=True,
                    truncation=True,
                    max_length=max_length,
                    return_tensors="pt",
                )
                tokens = {key: value.to("cuda:0") for key, value in tokens.items()}
                with torch.inference_mode():
                    hidden = model(**tokens).last_hidden_state[:, 0]
                    normalized = functional.normalize(hidden, p=2, dim=1)
                encoded_batches.append(normalized.cpu())
            return torch.cat(encoded_batches, dim=0)

        memory_texts = [str(item["natural_text"]) for item in memories]
        query_texts = [str(item["dense_query_text"]) for item in targets]
        query_prefix = str(config["encoding"]["query_prefix"])
        torch.cuda.reset_peak_memory_stats()
        started = time.monotonic()
        memory_embeddings = encode(memory_texts, lambda value: value)
        query_embeddings = encode(query_texts, lambda value: query_prefix + value)
        elapsed = time.monotonic() - started
        scores = query_embeddings @ memory_embeddings.T
        if not bool(torch.isfinite(scores).all()):
            raise RuntimeError("Dense similarities contain non-finite values")
        records = []
        for row, target_key in enumerate(target_keys):
            ordered = sorted(
                range(len(memory_keys)),
                key=lambda index: (-float(scores[row, index]), memory_keys[index]),
            )
            top = ordered[:10]
            records.append(
                {
                    "target_key": target_key,
                    "selected_memory_key": memory_keys[top[0]],
                    "selected_score": round(float(scores[row, top[0]]), 8),
                    "top10": [
                        {
                            "memory_key": memory_keys[index],
                            "score": round(float(scores[row, index]), 8),
                        }
                        for index in top
                    ],
                }
            )
        memory_norms = memory_embeddings.norm(p=2, dim=1)
        query_norms = query_embeddings.norm(p=2, dim=1)
        payload.update(
            {
                "status": "passed",
                "selection_passed": True,
                "timing": {"encoding_and_scoring_seconds": round(elapsed, 3)},
                "counts": {
                    "targets": len(targets),
                    "memories": len(memories),
                    "records": len(records),
                },
                "checks": {
                    "manifest_six_files": verification["checked"] == 6,
                    "memory_shape_100_by_1024": list(memory_embeddings.shape) == [100, 1024],
                    "query_shape_541_by_1024": list(query_embeddings.shape) == [541, 1024],
                    "unit_norm_memories": bool(
                        torch.all(torch.abs(memory_norms - 1.0) < 1e-5)
                    ),
                    "unit_norm_queries": bool(torch.all(torch.abs(query_norms - 1.0) < 1e-5)),
                    "unique_record_per_target": len(records)
                    == len({record["target_key"] for record in records})
                    == len(targets),
                },
                "peak_cuda_memory_mib": round(
                    torch.cuda.max_memory_allocated() / 1024 / 1024, 2
                ),
                "records": records,
            }
        )
        if not all(payload["checks"].values()):
            payload["status"] = "failed_check"
            payload["selection_passed"] = False
    except Exception as error:
        payload["status"] = "error"
        payload["selection_passed"] = False
        payload["error"] = f"{type(error).__name__}: {error}"
    write_result(output, payload)
    print(output)
    return 0 if payload["selection_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
