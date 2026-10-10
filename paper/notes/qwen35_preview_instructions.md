# Local Qwen3.5 preview of the V1 packet

This is a development-only diagnostic, not a replacement for Reviewer A or Reviewer B. It must not be cited as human blind review, inter-annotator agreement, or evaluator validation.

The preview script reads only the anonymous packet and writes a separate CSV using the packet's native six label columns (`decision_*`, `confidence`, and `notes`). It rejects sealed-key input and refuses to overwrite the reviewer templates. The output has the same CSV schema as a reviewer packet, but it remains a machine-generated development preview and is not a human review file.

## Safe first run

Start your local Qwen3.5 server in OpenAI-compatible mode, then run a 20-row preview:

```powershell
python paper/scripts/qwen35_blind_audit_preview.py `
  --model YOUR_LOCAL_QWEN35_MODEL_NAME `
  --base-url http://127.0.0.1:8000/v1 `
  --limit 20
```

For LM Studio, replace the port with its local server port. For an endpoint requiring a token, set `LOCAL_LLM_API_KEY` before invoking the script. Do not point `--input` at `sealed_key/`, and do not use either reviewer CSV as `--output`.

Before calling the model, validate packet parsing and inspect the exact anonymized payloads:

```powershell
python paper/scripts/qwen35_blind_audit_preview.py `
  --model placeholder `
  --limit 2 `
  --dry-run
```

The output default is `paper/generated/qwen35_v1_preview.csv`. It is deliberately separate from V1 and should not be included in any formal statistics.

To check a completed machine preview for blank/invalid labels and distributions, run:

```bash
python paper/scripts/summarize_qwen35_preview.py \
  --input paper/generated/qwen35_v1_preview_full.csv \
  --output paper/generated/qwen35_v1_preview_summary.json
```

This report is only a machine-output quality check; it is not an accuracy study.

## Direct use on the remote experiment machine

The supplied Qwen3.5 directory is `/home/amax/PycharmProjects/AINegoProject/src/Models/LLM/Qwen3.5-9B`. Run the script **on that Linux machine**, from the repository root, for a small development-only preview:

```bash
python paper/scripts/qwen35_blind_audit_preview.py \
  --backend transformers \
  --model-path /home/amax/PycharmProjects/AINegoProject/src/Models/LLM/Qwen3.5-9B \
  --device cuda:0 \
  --limit 20
```

This direct mode loads the local model with BF16, deterministic decoding, `local_files_only=True`, `trust_remote_code=False`, and a 256-token output cap. It should be treated as a small, non-formal preview only; do not run it over all 1,099 rows or add its labels to the V1 packet.

The script now logs model-load duration, GPU identity, every anonymized `pair_id`, strict-JSON parse status, per-row time, and an end-of-run status summary. To reduce terminal output on a larger preview, add `--progress-every 5`.
