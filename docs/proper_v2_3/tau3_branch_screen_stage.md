# PROPER v2.3 tau3 scripted branch-screen stage

## Decision

The pinned tau3-bench `v1.0.1` source now supplies 12 qualified **development-only scripted pairs** for a later model protocol. This does not create held-out or confirmatory capacity and does not authorize a model run.

The screen is CPU-only. It loads a fresh public database for every trace, calls the public airline or retail tool implementation, and uses the frozen PROPER v2.3 controller and complete ActionExecutionLedger. It does not execute a target task, load historical trajectories, load a model, or use a GPU.

## Exclusion audit

The stage re-hashes and reads the frozen PROPER v1 memory bank and the 12-pair PROPER v2 exposed manifest. It confirms five v1 failure provenances and five v2 semantic families, then keeps the new scripted failure families string-disjoint:

- `public_precondition_evidence_missing`;
- `stale_public_reference`;
- `outcome_unknown_requires_verification`.

This is a development overlap screen, not proof of semantic universality. The controller was frozen before these tau candidates were selected. Any future rule change caused by these pairs makes the affected pairs tuning inputs; they cannot be relabelled held-out.

## Candidate construction

All 12 candidate memberships come from the upstream train split: four read-only, four idempotent state-setting, and four non-idempotent side-effect positions across airline and retail. Each has at least two evaluator-required actions after the selected position.

Task ID, evaluator action, and continuation depth are audit-side metadata only. Native fixture arguments are selected independently from fresh public DB state. The PROPER method receives only an ActionSpec, public action-effect contract, observable evidence, and ActionExecutionLedger.

## Scripted branches

The three generic branches are:

1. pre-action public read obtains missing observable evidence and consumes the recovery memory;
2. a stale public reference fails visibly, the corrected absolute state setting succeeds, and a public read-back verifies it;
3. a non-idempotent action executes once but its response is suppressed, forcing read-only verification before the unknown ledger outcome is resolved.

Every trace must then permit two distinct ordinary planning actions and block an exact repeat of the successful recovery action. For non-idempotent actions, the guarded native tool must execute exactly once.

## Result and interpretation

The one-shot screen passed 12/12 pairs:

| Dimension | Result |
| --- | ---: |
| domains | 2 |
| read-only pairs | 4 |
| idempotent state-setting pairs | 4 |
| non-idempotent side-effect pairs | 4 |
| consumed lifecycle and ordinary-planning handoff | 12/12 |
| two scripted continuation actions allowed | 12/12 |
| exact successful recovery repeat blocked | 12/12 |
| non-idempotent action executed once and verified | 4/4 |

This establishes local scripted branch capacity only. It is not model completion evidence, not a selector result, and not confirmation of generalization. New held-out target capacity remains zero.

## Stop rule and next gate

If any development trace repeats a non-idempotent side effect, cannot verify an unknown outcome, fails to consume recovery memory, or cannot return to ordinary planning, the stage stops and preserves the negative output.

Because the scripted screen passed, the next gate is to freeze a five-condition development protocol—method, prompts, budgets, evaluator endpoints, exclusions, and input hashes—before any model run. That protocol must continue reporting selector, lifecycle, continuation, completion, safety, and cost separately.

## Local entry point

```powershell
python experiments/proper_v2_3/validate_tau3_branch_screen_v2_3.py --dependency-dir <tau3-runtime-dependency-folder>
```

Generated artifacts belong only under `outputs/proper_v2_3/tau3_branch_screen/`.
