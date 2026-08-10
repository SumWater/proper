from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PACKAGE_NAMES = (
    "torch",
    "transformers",
    "accelerate",
    "bitsandbytes",
    "sentence-transformers",
    "scikit-learn",
    "numpy",
    "scipy",
)

IMPORT_NAMES = (
    "torch",
    "transformers",
    "accelerate",
    "bitsandbytes",
    "sentence_transformers",
    "sklearn",
)


def run_command(args: list[str], cwd: Path | None = None) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            args,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "error": f"{type(exc).__name__}: {exc}"}
    return {
        "available": True,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def package_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for name in PACKAGE_NAMES:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def import_probes() -> dict[str, dict[str, Any]]:
    probes: dict[str, dict[str, Any]] = {}
    for name in IMPORT_NAMES:
        try:
            module = importlib.import_module(name)
        except Exception as exc:  # package import errors are diagnostic output
            probes[name] = {
                "imported": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
            continue
        record: dict[str, Any] = {
            "imported": True,
            "version": getattr(module, "__version__", None),
            "file": getattr(module, "__file__", None),
        }
        if name == "torch":
            cuda = getattr(module, "cuda", None)
            record["cuda_version"] = getattr(getattr(module, "version", None), "cuda", None)
            record["cuda_available"] = bool(cuda and cuda.is_available())
            record["cuda_device_count"] = int(cuda.device_count()) if cuda else 0
            if cuda and cuda.is_available():
                record["bf16_supported"] = bool(cuda.is_bf16_supported())
        probes[name] = record
    return probes


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_model_manifest(model_dir: Path, manifest: Path) -> dict[str, Any]:
    model_root = model_dir.expanduser().resolve()
    manifest_path = manifest.expanduser().resolve()
    failures: list[dict[str, str]] = []
    checked = 0
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        expected, separator, relative = line.partition("  ")
        if not separator or len(expected) != 64:
            failures.append({"entry": line, "reason": "invalid_manifest_line"})
            continue
        normalized = relative[2:] if relative.startswith("./") else relative
        candidate = (model_root / normalized).resolve()
        try:
            candidate.relative_to(model_root)
        except ValueError:
            failures.append({"entry": relative, "reason": "path_escapes_model_root"})
            continue
        checked += 1
        if not candidate.is_file():
            failures.append({"entry": relative, "reason": "missing_file"})
            continue
        actual = sha256_file(candidate)
        if actual != expected:
            failures.append(
                {
                    "entry": relative,
                    "reason": "sha256_mismatch",
                    "expected": expected,
                    "actual": actual,
                }
            )
    return {
        "model_dir": str(model_root),
        "manifest": str(manifest_path),
        "checked_file_count": checked,
        "failure_count": len(failures),
        "passed": checked > 0 and not failures,
        "failures": failures,
    }


def hash_model_directory(model_dir: Path) -> dict[str, Any]:
    model_root = model_dir.expanduser().resolve()
    entries: list[dict[str, Any]] = []
    for candidate in sorted(model_root.rglob("*")):
        if candidate.is_file():
            entries.append(
                {
                    "relative_path": candidate.relative_to(model_root).as_posix(),
                    "bytes": candidate.stat().st_size,
                    "sha256": sha256_file(candidate),
                }
            )
    manifest_payload = json.dumps(entries, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return {
        "model_dir": str(model_root),
        "file_count": len(entries),
        "total_bytes": sum(entry["bytes"] for entry in entries),
        "manifest_payload_sha256": hashlib.sha256(manifest_payload.encode("utf-8")).hexdigest(),
        "files": entries,
    }


def configured_model_roots(explicit: list[Path]) -> list[Path]:
    candidates = list(explicit)
    for variable in ("HF_HOME", "HUGGINGFACE_HUB_CACHE", "TRANSFORMERS_CACHE"):
        value = os.environ.get(variable)
        if value:
            candidates.append(Path(value))
    candidates.append(Path.home() / ".cache" / "huggingface" / "hub")

    roots: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        key = str(resolved)
        if key not in seen and resolved.is_dir():
            seen.add(key)
            roots.append(resolved)
    return roots


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"_read_error": f"{type(exc).__name__}: {exc}"}
    return value if isinstance(value, dict) else {"_value_type": type(value).__name__}


def directory_stats(path: Path) -> dict[str, int]:
    total_bytes = 0
    file_count = 0
    try:
        for child in path.rglob("*"):
            if child.is_file():
                file_count += 1
                total_bytes += child.stat().st_size
    except OSError:
        return {"file_count": file_count, "total_bytes": total_bytes}
    return {"file_count": file_count, "total_bytes": total_bytes}


def relative_depth(root: Path, path: Path) -> int:
    return len(path.relative_to(root).parts)


def find_model_configs(root: Path, max_depth: int) -> list[Path]:
    found: list[Path] = []
    for current, directories, filenames in os.walk(root):
        current_path = Path(current)
        try:
            depth = relative_depth(root, current_path)
        except ValueError:
            directories[:] = []
            continue
        if depth >= max_depth:
            directories[:] = []
        if depth <= max_depth and "config.json" in filenames:
            found.append(current_path / "config.json")
    return sorted(found)


def model_record(config_path: Path) -> dict[str, Any]:
    config = read_json(config_path)
    tokenizer_config_path = config_path.parent / "tokenizer_config.json"
    tokenizer_config = read_json(tokenizer_config_path) if tokenizer_config_path.is_file() else {}
    stats = directory_stats(config_path.parent)
    return {
        "path": str(config_path.parent),
        "config": {
            "_name_or_path": config.get("_name_or_path"),
            "model_type": config.get("model_type"),
            "architectures": config.get("architectures"),
            "torch_dtype": config.get("torch_dtype"),
            "vocab_size": config.get("vocab_size"),
            "hidden_size": config.get("hidden_size"),
            "num_hidden_layers": config.get("num_hidden_layers"),
            "quantization_config": config.get("quantization_config"),
            "read_error": config.get("_read_error"),
        },
        "tokenizer": {
            "tokenizer_class": tokenizer_config.get("tokenizer_class"),
            "has_chat_template": bool(tokenizer_config.get("chat_template")),
            "read_error": tokenizer_config.get("_read_error"),
        },
        **stats,
    }


def disk_record(path: Path) -> dict[str, Any]:
    usage = shutil.disk_usage(path)
    return {
        "path": str(path),
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
    }


def build_inventory(
    repo_root: Path,
    roots: list[Path],
    max_depth: int,
    verify_model_dir: Path | None,
    model_manifest: Path | None,
    hash_model_dirs: list[Path],
) -> dict[str, Any]:
    gpu_query = run_command(
        [
            "nvidia-smi",
            "--query-gpu=index,name,driver_version,memory.total,memory.free,compute_cap",
            "--format=csv,noheader,nounits",
        ]
    )
    models: list[dict[str, Any]] = []
    for root in roots:
        for config_path in find_model_configs(root, max_depth):
            models.append(model_record(config_path))

    manifest_verification = None
    if verify_model_dir is not None and model_manifest is not None:
        manifest_verification = verify_model_manifest(verify_model_dir, model_manifest)
    hashed_model_directories = [hash_model_directory(path) for path in hash_model_dirs]

    return {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "boundary": {
            "weights_loaded": False,
            "model_inference_run": False,
            "network_download_performed_by_script": False,
        },
        "host": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python_version": sys.version,
            "python_executable": sys.executable,
            "conda_default_env": os.environ.get("CONDA_DEFAULT_ENV"),
            "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        },
        "repository": {
            "root": str(repo_root),
            "head": run_command(["git", "rev-parse", "HEAD"], cwd=repo_root),
            "status": run_command(["git", "status", "--short"], cwd=repo_root),
        },
        "gpu": gpu_query,
        "gpu_processes": run_command(
            [
                "nvidia-smi",
                "--query-compute-apps=gpu_uuid,pid,used_memory,process_name",
                "--format=csv,noheader,nounits",
            ]
        ),
        "conda_environments": run_command(["conda", "env", "list", "--json"]),
        "packages": package_versions(),
        "imports": import_probes(),
        "model_manifest_verification": manifest_verification,
        "hashed_model_directories": hashed_model_directories,
        "scan": {
            "max_depth": max_depth,
            "roots": [str(root) for root in roots],
            "disks": [disk_record(root) for root in roots],
            "candidate_model_count": len(models),
            "candidate_models": models,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inventory a remote experiment machine without loading model weights."
    )
    parser.add_argument(
        "--model-root",
        action="append",
        default=[],
        type=Path,
        help="Model or cache root to scan; may be repeated.",
    )
    parser.add_argument("--max-depth", type=int, default=5)
    parser.add_argument(
        "--verify-model-dir",
        type=Path,
        help="Model directory whose files should be checked against --model-manifest.",
    )
    parser.add_argument(
        "--model-manifest",
        type=Path,
        help="sha256sum-style model manifest; requires --verify-model-dir.",
    )
    parser.add_argument(
        "--hash-model-dir",
        action="append",
        default=[],
        type=Path,
        help="Model directory to hash into the inventory; may be repeated.",
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.max_depth < 0:
        raise ValueError("--max-depth must be non-negative")
    if (args.verify_model_dir is None) != (args.model_manifest is None):
        raise ValueError("--verify-model-dir and --model-manifest must be provided together")
    repo_root = Path(__file__).resolve().parents[2]
    roots = configured_model_roots(args.model_root)
    inventory = build_inventory(
        repo_root,
        roots,
        args.max_depth,
        args.verify_model_dir,
        args.model_manifest,
        args.hash_model_dir,
    )
    rendered = json.dumps(inventory, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        sys.stdout.write(rendered)
    else:
        output = args.output.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
