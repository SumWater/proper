# Paper selector capacity audit v0.1

- Status: passed and locked before new formal model outputs
- Scope: model-free selection only
- Targets: 541
- Memory bank: 100 frozen development sources
- Result: `outputs/paper_2026/e1_selector_capacity/selector_capacity_audit.json`

## Boundary and reconstruction

The audit reconstructed 189 argument-omission, 175 transient-authorization, and 177 timeout targets
from the pinned ToolMisuseBench dev and public-test JSONL files. Cohort labels were used only to build
the three evaluation strata. Every selector decision consumed the observable failure-state mapping
and candidate policy-card mappings through the fail-closed paper boundary. No model was loaded and no
model output was read or generated.

The historical memory-bank manifest has LF line endings in the synchronized workspace while its
frozen file hash was created from CRLF serialization. Converting LF to CRLF in memory exactly recovers
the frozen SHA-256 `da06c653...`; the declared payload identity and all 100 rebuilt memory identities
also match. The audit records this as `lf_crlf_serialization_only` and does not rewrite the historical
artifact.

## Capacity result

| Stratum | Targets | Full changes | No-gate changes | No-gate vs full | No-contr. changes | No-contr. vs full |
|---|---:|---:|---:|---:|---:|---:|
| Argument omission | 189 | 120 | 130 | 10 | 120 | 0 |
| Transient authorization | 175 | 53 | 104 | 51 | 75 | 22 |
| Timeout | 177 | 32 | 66 | 34 | 46 | 14 |
| Total | 541 | 205 | 300 | 95 | 241 | 36 |

The union changed by at least one of the three variants contains 320 targets. This is not yet the E1
formal changed-target union, because Dense and LLM Judge selections must also be included before that
population is frozen.

## Risk diagnostics

At the coarse evaluator policy-class level, full PROPER's 205 active changes were all applicable. It
corrected 165 TF-IDF Rank-1 policy errors and introduced zero new policy errors. No-gate retained the
same 165 corrections but introduced 75 new errors; only 211/300 of its active changes were applicable.
This provides direct offline capacity for the conservative-gate ablation.

No-contradiction differed from full PROPER on 36 targets: 22 authorization and 14 timeout. Every one
was a retry choice with an exhausted public retry budget. The benchmark's coarse policy-class label
marks retry as theoretically applicable, but the observable execution contract cannot authorize a
retry after budget exhaustion. Therefore the paper must report both diagnostics and must not describe
the coarse label alone as executable applicability. This provides direct capacity for the
contradiction ablation and clarifies its safety role.

## Decision

The capacity gate passes. The shared selector, observable retry-safety taxonomy, strict abstention
semantics, and two single-component ablations are frozen as `proper_paper_2026_v0_1_frozen`. This
freeze authorizes continued E1 non-model baseline preparation; it does not authorize formal agent
generation, which remains blocked on the remaining P0 items.
