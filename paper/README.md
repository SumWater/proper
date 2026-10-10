# PROPER paper workspace

This directory contains the paper-only F1/W1 artifacts for the frozen P0--E5 study. It excludes E6 and Tau3 evidence by design.

## Rebuild generated tables

From the repository root:

```powershell
python paper/scripts/generate_f1_artifacts.py
```

The script reads five explicitly named, hash-locked P0--E5/V1-preparation files. It fails closed on any hash mismatch and never scans `outputs/paper_2026` recursively. Generated LaTeX tables are written to `paper/tables/`; their source identities are recorded in `paper/generated/provenance_manifest.json`.

To recheck the clone restoration whitelist against the original experiment repository:

```powershell
python paper/scripts/verify_restored_inputs.py
```

This verifies exactly 54 files and writes their source/target hashes to `paper/generated/restoration_manifest.json`; the list is explicit and rejects E6/Tau3 paths.

## Evidence policy

- `notes/evidence_inventory.md` is the canonical number-level evidence ledger.
- `notes/claim_evidence_matrix.md` separates confirmatory, sensitivity, descriptive, and incomplete-V1 claims.
- Frozen outputs, configurations, result locks, and existing statistics are read-only.
- `TODO-V1` marks claims that cannot enter the submission until blinded human review and agreement analysis are complete.
- E6/Tau3 materials are out of scope and must not be cited, copied, scanned, or used to strengthen the narrative.

## Current state

The evidence audit, initial positioning, complete outline, English LaTeX skeleton, and five generated tables are present. Related-work citations, venue formatting, and V1 human labels remain open.
