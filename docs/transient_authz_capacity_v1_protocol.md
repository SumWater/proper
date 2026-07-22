# Transient authorization extension: CPU capacity protocol

## Scope

This extension is restricted to ToolMisuseBench's released transient
authorization condition. It does not claim to solve persistent authorization
or to infer recoverability from the first denial. Retrying a persistent denial
remains a Safety Violation and is explicitly outside the method's scope.

The public-test authorization inputs have been acquired previously, but no
native-authorization model output has been generated. This stage is therefore
a model-output holdout capacity audit, not an unseen-input claim.

## Selector

The selector sees only the agent-visible first `authz_denied` observation and
the frozen TF-IDF Top-10 candidate experiences. If Rank-1 already recommends
retry, it is preserved exactly. Otherwise the selector chooses a retry memory,
preferring the same tool and then the original TF-IDF order. Fault plans,
recoverability, provenance, applicability labels, and recovery outcomes are
forbidden selector inputs.

The evaluator uses the released fault label only to construct the transient
authorization cohort and verifies that one retry is valid in that released
environment. Those labels never enter the selector or prompt.

## Capacity gate

Before any new GPU run, CPU preparation must find at least 50 valid native
authorization targets and at least 20 cases where the selector changes Rank-1.
Changed cases must cover at least three target tools and three selected
memories; no single selected memory may exceed 50% of changed cases. Thirty
changed pairs is the preferred capacity. All 189 source task IDs from the
completed argument-omission experiment are excluded and source/target split
isolation remains dev-memory versus public-test target.

Passing this gate authorizes only preparation of a new paired protocol. It does
not authorize a GPU run or establish Recovery Validity improvement.
