from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = Path(r"C:\Users\tanyang\Desktop\大模型\小论文\proper")

# Explicit P0--E5 locks only. E6/Tau3 locks are intentionally absent.
LOCKS = (
    "configs/paper_2026/agent_evaluation_v1_0.result.lock.json",
    "configs/paper_2026/agent_generation_v1_0.result.lock.json",
    "configs/paper_2026/agent_prompt_cache_v1_0.result.lock.json",
    "configs/paper_2026/dense_retrieval_v0_1.result.lock.json",
    "configs/paper_2026/e1_dense_selection_v1_0.result.lock.json",
    "configs/paper_2026/e1_llm_judge_selection_v1_0.result.lock.json",
    "configs/paper_2026/e1_selection_v1_0.result.lock.json",
    "configs/paper_2026/e2_e3_analysis_v1_0.result.lock.json",
    "configs/paper_2026/e4_diagnostics_v1_0.result.lock.json",
    "configs/paper_2026/e5_concentration_v1_0.result.lock.json",
    "configs/paper_2026/evaluator_blind_audit_v1_0.preparation.lock.json",
    "configs/paper_2026/llm_judge_v0_1.result.lock.json",
    "configs/paper_2026/model_b_manifest_v0_1.lock.json",
    "configs/paper_2026/selector_capacity_audit_v0_1.result.lock.json",
)

# Direct dependencies named by frozen configs but not represented as path/sha256
# objects in the result locks.
EXTRAS = {
    "outputs/paper_2026/e1_selection/deterministic_selections.json": "60c03e9ffd4da1f2dd8be592e4b6ffb87e12d113b9b3d0f55642af02e637b8a3",
    "outputs/paper_2026/e1_selection/observable_inputs.json": "a48cfb02cc3ec2aeb3f4edadd5793ed356991bc5adf7509d5b1360f5e6dbf544",
    "outputs/paper_2026/e1_selection/preparation_manifest.json": "b297256018d386cced2e1212b704bf8303a63397d74f9bc9d109b6494ac68253",
    "outputs/paper_2026/e1_selection/oracle_private.json": "d81bb442ef708f833f906acb0848ba31261f1fd8ad7e79f0b425b0ece2dcf618",
    "outputs/paper_2026/p0_environment_lock.json": "fb943ddec5a962883c0e70cd1b863ad8c5547a0847107a76a175b53174a02443",
    "outputs/paper_2026/p0_conda_probe.json": "a71f30a3b550b38eefd2fea3a5fde0646768a94898af83eefba4f5e3ac106f60",
    "outputs/paper_2026/p0_remote_storage.json": "a4576f8a07ec028c6ac8e896296e4a4dc5e6398e565297a6c365fae97623aa3b",
}

P0_RESTORED = (
    "outputs/paper_2026/p0_smoke_qwen3_8b.json",
    "outputs/paper_2026/p0_smoke_bge_large_en_v1_5_attempt1_runner_symlink_bug.json",
    "work/toolmisusebench_sample/dev.jsonl",
    "work/toolmisusebench_test/test_public.jsonl",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def collect_from_node(node: Any, destination: dict[str, str]) -> None:
    if isinstance(node, dict):
        path = node.get("path")
        digest = node.get("sha256")
        if isinstance(path, str) and isinstance(digest, str) and path.startswith("outputs/paper_2026/"):
            destination[path] = digest
        checkpoint_path = node.get("checkpoint_path")
        checkpoint_digest = node.get("checkpoint_sha256")
        if isinstance(checkpoint_path, str) and isinstance(checkpoint_digest, str):
            destination[checkpoint_path] = checkpoint_digest
        for value in node.values():
            collect_from_node(value, destination)
    elif isinstance(node, list):
        for value in node:
            collect_from_node(value, destination)


def p0_manifest() -> dict[str, str]:
    result = {}
    for line in (ROOT / "configs/paper_2026/p0_local_sources.sha256").read_text(encoding="utf-8").splitlines():
        if line:
            digest, relative = line.split("  ", 1)
            result[relative] = digest
    return result


def main() -> None:
    whitelist: dict[str, str] = {}
    for relative in LOCKS:
        collect_from_node(json.loads((ROOT / relative).read_text(encoding="utf-8")), whitelist)
    whitelist.update(EXTRAS)
    p0 = p0_manifest()
    for relative in P0_RESTORED:
        whitelist[relative] = p0[relative]

    records = []
    failures = []
    for relative, expected in sorted(whitelist.items()):
        if "e6" in relative.lower() or "tau3" in relative.lower():
            raise RuntimeError(f"out-of-scope whitelist entry: {relative}")
        target = ROOT / relative
        source = SOURCE_ROOT / relative
        target_digest = sha256(target) if target.is_file() else None
        source_digest = sha256(source) if source.is_file() else None
        state = "ok" if target_digest == source_digest == expected else "failed"
        record = {
            "path": relative,
            "expected_sha256": expected,
            "source_sha256": source_digest,
            "target_sha256": target_digest,
            "state": state,
        }
        records.append(record)
        if state != "ok":
            failures.append(record)
    if len(records) != 54:
        raise RuntimeError(f"restoration whitelist size changed: {len(records)} != 54")
    output = {
        "schema_version": 1,
        "scope": "P0-E5 agent generation/evaluation, selector, statistics, and V1 preparation; E6/Tau3 excluded",
        "source_root": str(SOURCE_ROOT),
        "target_root": str(ROOT),
        "file_count": len(records),
        "failure_count": len(failures),
        "records": records,
    }
    path = ROOT / "paper/generated/restoration_manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if failures:
        raise RuntimeError(json.dumps(failures, indent=2))
    print(json.dumps({"status": "ok", "files": len(records), "failures": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
