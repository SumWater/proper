# PROPER v2.3 prospective target-capacity audit protocol

## Purpose and current decision

This is an input-only, no-model, no-play audit design. The frozen ToolSandbox
inventory already evaluated 1,032 scenario names and produced zero eligible
new continuation candidates. That pool is exhausted under the current
exclusion rules and will not be relabelled as held-out capacity.

No new target source is currently registered. The present disposition is
therefore `stop_no_target_capacity`. The protocol defines how a genuinely new
source would be screened later; it does not claim that one exists.

## Source requirements

A source must be outside the exhausted ToolSandbox inventory and provide:

- public task instructions and tool schemas;
- public evidence sufficient to classify action effects;
- an observable, reproducible recovery branch without model play-through;
- at least two necessary task steps after recovery;
- multiple failure-policy families;
- multiple action-effect classes;
- a behaviorally identifiable selector, lifecycle, or controller contrast.

Targets that require hidden recoverability, gold actions, evaluator outcomes,
or scenario-specific method branches are ineligible.

## Exclusions

Before screening, a source-level manifest must exclude:

- the 12 Qwen-exposed development targets;
- variants of their semantic families;
- protected memory-source families;
- every target used to tune a v2.3 rule;
- every target with previously inspected model output.

Semantic-family and scenario metadata are permitted only in this audit-side
exclusion process. They are forbidden in the method implementation.

## Prospective partition

Before any target model output, surviving targets must be assigned immutably
to:

1. development;
2. held-out;
3. preservation.

A target cannot move from development to held-out. Capacity inspection makes
the input model-output holdout rather than fully unseen-input holdout.

## Frozen capacity gates

The initial design requires:

- at least 2 independent semantic families;
- at least 12 behaviorally distinct pairs;
- at least 3 non-idempotent side-effect pairs;
- at least 3 idempotent state-setting pairs;
- at least 3 read-only or verification pairs.

These thresholds are development design gates, not statistical power claims.
Any later confirmatory protocol must separately prespecify sample size,
paired analysis, endpoints, exclusions, and stopping rules.

## Audit output

The audit records:

- source and input hashes;
- exclusion counts and reasons;
- public effect-evidence availability;
- recoverable-branch and continuation-depth checks;
- effect and failure-policy diversity;
- prospective partition identity;
- model/GPU authorization flags;
- explicit stop disposition.

The audit never loads a model, reads a target model output, or plays a target
scenario.

## Stop rules

- No genuinely unexposed targets: `stop_no_target_capacity`.
- Duplicate non-idempotent side effects in development:
  `stop_safety_gate`.
- No post-failure completion improvement:
  `stop_completion_gate`.

The current repository remains at the first stop condition.
