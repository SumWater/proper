# PROPER v2.3 observable action-execution contract

## Status

This is the first development contract for PROPER v2.3. It was created after
the frozen v2.2.1 result and before any v2.3 model output. It does not alter
the v1 paper core, the frozen v2.x methods, or their results.

The contract is development-only. It authorizes neither a GPU run nor a
confirmatory claim.

## Research boundary

The execution controller accepts the same public interface in `pre_action`
and `post_failure`:

```text
ObservableRecoveryState
+ selected MemoryPolicyCard
+ MemoryLifecycleState
+ ActionExecutionLedger
+ proposed action and public action-effect contract
-> allow | verify | replan | stop
```

Scenario names, semantic-family names, hidden recoverability, benchmark gold
actions, evaluator outcomes, prior model results, and matched-memory labels
are not method inputs.

The controller does not infer semantics from a tool name. Action effects,
retry safety, and verification support require explicit public evidence from
a tool schema, public environment contract, or visible runtime observation.

## Two-axis action representation

Action effect and execution outcome are separate axes.

### Effect class

| Class | Meaning | Default repeat rule |
|---|---|---|
| `read_only` | Public contract says the action does not mutate task or external state. | A successful exact action is not repeated. A distinct bounded read-only verification may be allowed. |
| `idempotent_state_setting` | Reapplying the same absolute state is publicly idempotent. | A successful exact action is not repeated. Unknown outcomes are verified when a public query exists. |
| `non_idempotent_side_effect` | The action can create another external effect, such as another delivery. | Success and unknown outcome both prohibit blind repetition. |
| `unknown_effect` | Public evidence cannot classify the effect. | Fail closed before execution. |

Known retry safety is independent of effect class and must have its own public
evidence. A failed action may be retried only when the contract marks retry as
`safe` and retry budget remains. Success never becomes retry authority.

For one normalized action, effect class, classification evidence, and
verification contract remain stable across the trajectory. Runtime retry
safety may move from `unknown` to `safe` or `unsafe` only when the new public
evidence is additive. A known status cannot be removed or flipped.

### Execution status

Every proposal is retained in the full trajectory ledger:

```text
proposed -> executed -> succeeded
                     -> failed
                     -> outcome_unknown -> succeeded | failed
```

A blocked proposal remains `proposed`, records the controller disposition,
and cannot transition to `executed`. Success and failure are terminal.
`outcome_unknown` may be resolved once by later observable evidence.

## Normalized action identity

Exact identity is SHA-256 over canonical UTF-8 JSON containing:

- the public tool name;
- recursively key-sorted JSON arguments;
- original list order;
- no scenario, evaluator, or memory identity.

This is deliberately an exact identity, not semantic equivalence. V2.3 does
not guess that two differently represented requests have the same effect.
Future equivalence broadening would require a separately frozen public
contract and new development evidence.

## Complete ActionExecutionLedger

The ledger covers recovery, ordinary-task, and verification actions. Each
entry records:

- deterministic entry and sequence identity;
- normalized action identity;
- decision phase and action purpose;
- effect class and its public evidence;
- retry-safety status and evidence;
- proposed, executed, succeeded, failed, or unknown status;
- success/failure evidence with provenance and step;
- controller disposition and reason;
- related prior entries, including blocked repeats and verified executions.

The ledger is execution state, not actionable memory. It contains no natural
memory text, retrieval score, benchmark label, or gold trajectory.

## Lifecycle and controller rules

The memory states remain:

- `active`: memory-guided planning;
- `consumed`: recovery success or trigger clearance is verified and ordinary
  task planning resumes;
- `failed`: observable conflict or unverifiable unsafe state fails closed;
- `stopped`: task completion, safe stop, or exhausted controller guard.

Rules applied to every action in the trajectory:

1. A new publicly classified action may be `allow`ed.
2. An exact successful action is never executed again. The proposal receives
   `replan`, then `stop` if replan budget is exhausted.
3. A non-idempotent or state-changing action with `outcome_unknown` is not
   retried. A declared read-only verifier may receive `verify`.
4. Other work cannot proceed while required verification is unresolved. A
   successful exact verification action is not repeated.
5. A failed exact action receives `allow` only with explicit safe-retry
   evidence and remaining retry budget.
6. An active `stop_and_report` memory blocks every tool action.
7. A successful recovery consumes the memory only when success evidence is
   satisfied or its trigger is observably cleared.
8. Success evidence with a still-active trigger enters `failed`.
9. Explicitly violated runtime success evidence enters `failed` even if a
   separate trigger-clearance signal is present.
10. Missing verification support, unknown effect, or exhausted required budget
   has a machine-readable fail-closed reason.

The v2.3 observable boundary also rejects scenario name, semantic family,
gold action or label, evaluator outcome, prior model result, and the forbidden
v2 fields recursively.

The current controller protects exact normalized actions. It does not yet
claim semantic duplicate detection across different arguments or tools.

## Independent budgets

The frozen development defaults are:

- retry: 1;
- verification: 2;
- invalid decision: 1;
- replan: 2.

Each event decrements only its own budget. Invalid decisions do not consume
general replan budget; verification does not consume retry budget; blocked
successful repeats do not consume retry budget. Exhaustion is reported
separately.

## Development reporting

Any later model-development result must keep these endpoints separate:

- selector first-decision alignment;
- lifecycle transition and evidence;
- recovery continuation;
- final task completion and partial progress;
- repeated actions by effect class;
- duplicate non-idempotent side effects;
- unknown outcomes and verification;
- model requests, accepted actions, tool calls, tokens, and controller
  overhead.

The existing 12 pairs remain development regression data and cannot become
held-out or confirmatory evidence.

## Stop boundary

Development stops rather than tuning the same frozen protocol when:

- no genuinely unexposed target capacity is available;
- any duplicate non-idempotent side effect remains in development;
- post-failure final completion shows no improvement.

No model runner is part of this first stage.
