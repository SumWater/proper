from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ID = "mistralai/Mistral-7B-Instruct-v0.3"
REVISION = "c170c708c41dac9275d15a8fff4eca08d52bab71"
ALLOW_PATTERNS = (
    "README.md",
    "config.json",
    "generation_config.json",
    "model-*.safetensors",
    "model.safetensors.index.json",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer.model",
    "tokenizer_config.json",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest(model_dir: Path) -> dict[str, Any]:
    files = []
    for path in sorted(model_dir.rglob("*")):
        if path.is_file() and ".cache" not in path.relative_to(model_dir).parts:
            files.append(
                {
                    "relative_path": path.relative_to(model_dir).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    payload = json.dumps(files, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "repo_id": REPO_ID,
        "revision": REVISION,
        "model_dir": str(model_dir),
        "file_count": len(files),
        "total_bytes": sum(item["bytes"] for item in files),
        "manifest_payload_sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "files": files,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download and hash the frozen paper model B.")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--manifest-output", required=True, type=Path)
    parser.add_argument(
        "--execute-download",
        action="store_true",
        help="Required acknowledgement that this command performs a network download.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.execute_download:
        raise RuntimeError("download blocked: pass --execute-download after user authorization")
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise RuntimeError("huggingface_hub is required in the selected environment") from exc

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    downloaded = Path(
        snapshot_download(
            repo_id=REPO_ID,
            revision=REVISION,
            allow_patterns=list(ALLOW_PATTERNS),
            local_dir=str(output_dir),
        )
    ).resolve()
    result = manifest(downloaded)
    manifest_output = args.manifest_output.expanduser().resolve()
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(manifest_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

