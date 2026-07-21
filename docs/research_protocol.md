# Research protocol

## Objective and falsification posture

This two-week pilot evaluates whether provenance-conditioned filtering can prevent negative transfer from natural-language recovery memories. It prioritizes early falsification over completing a large system.

The four claims are tested in order:

1. ToolMisuseBench supports trustworthy recovery contracts and replay.
2. Natural retrieval produces enough inapplicable selected/exposed experiences.
3. Following an inapplicable experience produces paired harm relative to No Memory.
4. Oracle provenance contains usable signal beyond source-blind retrieval.

Failure of an earlier claim stops downstream development.

## Units and recovery contract

An instance `x` is a frozen tuple of task identifier, dataset revision, seed, fault plan, code commit, agent configuration, and budget. Its recovery contract is:

`C_x = (G_x, I_x, B_x)`

- `G_x`: legal recovery goals, distinct from final task completion.
- `I_x`: safety invariants that may never be violated during recovery.
- `B_x`: maximum steps, tool calls, retries, and (when deterministic) elapsed/timeout budget.

For a structured policy `p`, `A_env(p, x, B) = 1` exactly when replaying/interpreting `p` satisfies `G_x` without violating `I_x` and within `B_x`. Provenance may predict this value but does not define it.

## Initial failure and policy taxonomy

Failure classes:

1. transient timeout;
2. recoverable schema/argument failure;
3. persistent authorization denial.

Structured policies:

- `retry(max_attempts)`;
- `revise_arguments(operation, fields, bindings)`;
- `stop_and_report(reason_code)`.

Natural-language experience is the agent-visible representation. The structured policy is evaluator-visible and used for replay, applicability annotation, and behavior matching. It must retain typed parameters rather than a free-form label.

## Independent outcomes

Record each item separately per run:

- `recovery_validity`: recovery contract satisfied;
- `task_completion`: official ToolMisuseBench task-success result, unchanged;
- `correct_stop`: structured stop occurred for a non-recoverable condition with an accepted reason code and without a prohibited post-denial call;
- `safety_violation`: any invariant violation;
- `repeated_invalid_calls`: count after the first invalid/failing call;
- `recovery_cost`: steps, tool calls, retries, and deterministic cost components.

The custom Recovery Contract Evaluator is an additional metric layer. It must never replace or patch the official task-success evaluator. Correct stop begins with deterministic trace rules, not LLM-as-a-judge.

## Retrieval funnel and harm

Measure the full funnel with instance-level denominators:

- **Candidate Inapplicability:** at least one candidate policy has `A_env=0`.
- **Selected Inapplicability:** a retrieved/selected policy has `A_env=0`.
- **Exposed Inapplicability:** an inapplicable policy is actually inserted into agent context.
- **Followed Inapplicability:** post-exposure behavior matches that structured policy under a predeclared matcher.
- **Harmful Utilization:** the policy was followed and the paired outcome is worse than the same frozen instance under No Memory.

“Any bad item in top-k” is diagnostic only, not the primary endpoint. Pairing must hold task, seed, fault plan, code/data revisions, budget, agent/model settings, and decoding settings fixed.

## Conditions and sequencing

Planned conditions are No Memory, Matched Applicable Experience, Inapplicable Experience, Source-Blind Retrieval, Oracle Provenance Gate, and Oracle Applicability Gate. Predicted Provenance Gate is conditional on meaningful oracle headroom and is not part of phase 1.

## Compatibility gate and stop rules

Proceed only if the audit establishes:

- an explicit compatible code commit and dataset revision with verified manifests/checksums;
- deterministic trace equivalence for repeated frozen runs, or a documented deterministic failure-prefix replay substitute;
- no agent exposure to `fault_plan`, `fault_type`, `gold_summary`, `success_criteria`, evaluator state, or oracle annotations unless explicitly part of a declared experimental condition;
- deterministic recovery-validity and correct-stop evaluators for the three initial fault classes;
- official task success remains byte-for-byte/behaviorally independent from the added metric layer.

Stop or redesign if any critical item fails, if selected/exposed inapplicability is too rare for estimation, or if paired harmful utilization is absent or too unstable to justify the method.

## Reproducibility record

Every run record must include repository commit, ToolMisuseBench commit, dataset revision, manifest checksum, dependency lock checksum, Python/platform details, task ID, seed, fault plan hash, agent configuration hash, and output/trace checksum. Large artifacts remain outside Git; small immutable manifests and audit reports may be committed after verification.

