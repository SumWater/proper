# Paper selector design v0.1

- Status: frozen after offline three-stratum capacity audit and before formal model outputs
- Method version: `proper_paper_2026_v0_1_frozen`
- New formal model outputs inspected during implementation: no
- Historical outputs previously known: yes; see `protocol.md`

## Purpose and lineage

The paper selector is implemented under `src/failure_memory/paper_2026/`. It reuses the typed
observable-state, memory-policy-card, and contradiction primitives from PROPER v2 but does not modify
the historical v1/v2 selectors or their frozen outputs. The paper layer exists to make the full method
and its two prespecified ablations separable and auditable under one interface.

## Interface

The selector consumes one `ObservableFailure` or `ObservableRecoveryState` plus a contiguous Rank-1
through Rank-k list of `MemoryPolicyCard` values. It returns exactly one action:

- `keep_rank1`: Rank-1 is the best positively supported admissible candidate;
- `select`: a named alternative is authorized to replace Rank-1;
- `abstain`: the selector declines to intervene and preserves Rank-1 as the retrieval fallback.

Abstention does not assert that Rank-1 is applicable. The selected identity is always recorded so the
downstream injected prompt is unambiguous.

## Component separation

Candidate ordering uses, in sequence, active contradiction count, positive evidence support,
precondition status, repair-target agreement, trigger-evidence agreement, tool compatibility,
extraction confidence, original rank, and lexical experience ID.

The full method replaces Rank-1 only when the best alternative:

1. has no active contradiction;
2. has positive operation-specific support in public evidence; and
3. is decisively superior to Rank-1 on contradiction count, evidence support, precondition status, or
   repair-target agreement.

`PROPER-no-gate` retains contradiction checking but removes requirements 2 and 3. It selects the best
contradiction-free candidate. `PROPER-no-contradiction` records detected contradictions for audit but
removes them from eligibility and ordering, while retaining requirements 2 and 3. No other component
changes between variants.

## Input boundary

The paper boundary rejects benchmark, dataset, split, scenario, method, condition, applicability,
oracle, gold-action, hidden-label, and prior-model-outcome fields recursively. The inherited v2
boundary additionally rejects fault plans, recoverability, evaluator outcomes, provenance, and other
injection-only metadata. Candidate input order cannot affect a decision; ranks must be unique and
contiguous from 1.

## Verification completed

Ten new paper-selector tests pass. Together with the relevant v1/v2 boundary and selector suites,
37 focused tests pass. They cover component isolation, strict fallback semantics, deterministic order,
rank validation, variant recording, and recursive rejection of hidden fields.

The full local suite ran 267 tests: the new and focused tests passed, while six errors and one failure
remain in unrelated historical tests because this workstation lacks several `work/` artifacts and the
pinned ToolSandbox checkout; 14 external-resource tests were skipped. These are environment-fixture
limitations, not regressions attributed to the paper selector.

## Capacity gate result

The model-free audit reconstructed all 541 targets (189 argument omission, 175 transient
authorization, and 177 timeout) from frozen raw inputs and the 100-source memory bank. Full PROPER
changed 205 TF-IDF identities. The no-gate and no-contradiction ablations produced respectively 95
and 36 prompt-identity differences from full PROPER, so both planned behavior comparisons have
non-zero capacity.

Full PROPER's 205 active replacements were all evaluator-policy-applicable and corrected 165 Rank-1
policy errors with zero new policy errors. Removing the gate produced 75 new policy errors. Removing
contradiction checking authorized 36 retry selections whose public retry budgets were exhausted; the
coarse environment policy label still marks the retry policy class applicable, so that label must not
be misreported as executable under the observable contract. Full details are in
`selector_capacity_audit_v0_1.md`.
