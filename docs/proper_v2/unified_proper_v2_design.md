# Unified PROPER v2 design

## Status and purpose

This document defines the first development interface for unified PROPER v2.
It is a method specification, not a confirmatory preregistration and not new
Recovery Validity evidence.

Completed PROPER v1 model outcomes may be used for regression tests and
descriptive development analysis only. They must not be used to tune v2 and
then be presented again as independent confirmation.

## Research objective

PROPER v2 asks whether one conservative, observable-evidence-only memory
selector can improve retrieval across representative recovery settings while
controlling negative transfer and safety risk.

The intended claim is broad applicability across representative settings. No
finite experiment can establish applicability to every possible Agent memory
setting.

## Method boundary

The selector may use only information available to the Agent before memory
selection:

- task text;
- public tool names and schemas;
- the failed action and its arguments;
- public error codes, messages, and ordinary error details;
- sanitized execution history;
- remaining public budgets;
- public environment guarantees;
- natural-language candidate memories;
- structured fields extracted from those memories;
- original retrieval rank and score.

The following information is forbidden recursively:

- benchmark fault plans or hidden fault types;
- hidden recoverability;
- gold summaries or gold trajectories;
- evaluator applicability labels;
- Recovery Validity, task-completion, or safety outcomes;
- matched-oracle memory identifiers;
- injection-only metadata;
- test-split difficulty or solution metadata unavailable to the Agent.

The boundary rejects forbidden data. It does not silently use or transform it.

## Observable decision-state representation

The frozen v2 `ObservableFailure` remains the backward-compatible
post-failure representation.

PROPER v2.1 adds `ObservableRecoveryState`, which explicitly separates:

- `pre_action`: the Agent is considering an action but has not executed it;
- `post_failure`: an attempted action has produced an observable failure.

This distinction is required because an insufficient-information minefield
cannot be safely evaluated by first executing the prohibited action. Both
phases use the same memory-policy cards, compatibility evaluator, and
conservative selector. Model outcomes must nevertheless be reported by phase
instead of pooling unlike evaluation times into one confirmatory test.

The unified representation includes:

- instruction;
- contemplated or failed action, which may be absent before action;
- public error code;
- normalized evidence codes;
- missing fields and public schema fields;
- available tools and capabilities;
- satisfied and violated public facts;
- repeated identical call count (`0` before action);
- retry-safety status and its public evidence.

`pre_action` states cannot contain an error code or failed-argument paths,
must have a repeated-call count of zero, and cannot claim known retry safety.
`post_failure` states require a failed action and a positive repeated-call
count.

Retry safety is three-valued:

- `safe`: public evidence authorizes a bounded retry;
- `unsafe`: public evidence prohibits a retry;
- `unknown`: no public evidence distinguishes safe from unsafe retry.

An error name such as `timeout` or `authz_denied` does not, by itself, make a
retry safe. Safety must come from a public environment contract or observable
execution evidence.

## Memory policy representation

Each candidate becomes a `MemoryPolicyCard`:

```text
trigger evidence
+ required preconditions
+ recovery operation
+ target object
+ proposed action
+ repair targets
+ continuation policy
+ success evidence
+ stop conditions
+ provenance-safe source tool
+ extraction confidence
+ original retrieval identity
```

Recovery operation is one of:

- `repair_arguments`;
- `retry_same_action`;
- `invoke_prerequisite`;
- `switch_tool`;
- `use_fallback`;
- `request_information`;
- `stop_and_report`;
- `unknown`.

Continuation policy is represented separately:

- `continue_directly`;
- `verify_then_continue`;
- `retry_then_verify`;
- `terminate`;
- `unknown`.

This separation allows multi-step policies such as “invoke prerequisite,
verify, then retry” without treating `verify` as a mutually exclusive
top-level recovery class.

## Preconditions and compatibility

Required preconditions use three-valued evaluation:

- `satisfied`: every required fact is publicly satisfied;
- `violated`: at least one required fact is publicly violated;
- `unknown`: no violation is known, but at least one fact is unobserved.

Candidate compatibility is also three-valued:

- `compatible`;
- `uncertain`;
- `incompatible`.

Known contradictions make a candidate ineligible. Initial contradiction codes
cover:

- violated precondition;
- direct retry without explicit safe-retry evidence;
- proposed tool unavailable;
- switch-tool policy that does not actually switch tools;
- repair target absent from the public schema;
- repair target inconsistent with a public missing-field error;
- operation marked `unknown`;
- extraction confidence below the frozen minimum.

V2.1 additionally rejects retry and argument-repair policies in a
`pre_action` state because no failed action exists to retry or repair.

The vocabulary may be extended only during declared development and must be
frozen before unused model outputs are generated.

## Conservative selection

PROPER v2 evaluates all candidates through the same function. It does not
branch on benchmark provenance or hidden failure labels.

The selector:

1. validates the observable boundary;
2. validates candidate identity and original ranks;
3. computes contradictions and precondition status;
4. evaluates operation support, repair agreement, trigger agreement, and tool
   compatibility;
5. orders candidates deterministically;
6. replaces Rank-1 only when the best alternative is contradiction-free,
   explicitly compatible, and decisively superior on a primary compatibility
   dimension;
7. otherwise retains Rank-1 and records abstention.

Retrieval score and original rank break ties only after public compatibility
dimensions. They cannot by themselves authorize an intervention.

An abstention means that PROPER declines to change the retrieval result. It
does not claim that Rank-1 is applicable.

## Decision record

Every selection produces a `SelectionDecision` with:

- selected and Rank-1 identities;
- changed and abstained flags;
- reason codes;
- threshold identity;
- ordered candidate evaluations;
- contradictions;
- precondition status;
- compatibility;
- evidence-agreement measures;
- deterministic sort components.

The record must contain enough information to independently reconstruct why
an intervention occurred.

## Development and freezing rules

Before a new model-output experiment:

- freeze schemas and source hashes;
- freeze memory bank and Top-k;
- freeze extraction rules and confidence threshold;
- freeze compatibility and contradiction rules;
- freeze intervention criteria;
- freeze dataset identity and exclusions;
- freeze prompt, model, decoding, evaluator, and result schema;
- perform a CPU-only capacity audit;
- stop if capacity, diversity, identifiability, or safety gates fail.

CPU capacity auditing may inspect public inputs and evaluator applicability
only for capacity labels. It must not read or generate model outputs. Inputs
used for capacity gating are model-output holdout data, not fully unseen-input
holdout data.

## Planned validation sequence

1. Unit-test the unified representation and conservative invariants.
2. Adapt v1 development artifacts for descriptive regression only.
3. Freeze and run a CPU-only timeout capacity audit.
4. Run a timeout model experiment only if capacity and safety gates pass.
5. Audit an external stateful benchmark for prerequisite, switch, fallback,
   verification, and information-request policies.
6. Complete a frozen cross-model replication regardless of whether the first
   valid external result is positive, null, or negative.
