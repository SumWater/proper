# PROPER v2 cross-failure capacity audit

## Decision

`STOP_DIRECT_ONE_STEP_PROPER_V2_GPU_RUN`

The frozen 332-target development manifest was audited without loading a model,
reading model outputs, refitting the gate, or authorizing a GPU run. The audit
measures candidate capacity and observable identifiability; it is not Recovery
Validity evidence.

## Capacity by failure family

| Family | Targets | Tools | Rank-1 applicable | Rank-1 bad, Top-10 replacement | Replacement memories | Readiness |
|---|---:|---:|---:|---:|---:|---|
| Schema drift | 94 | 9 | 94 | 0 | 0 | preservation control only |
| Timeout | 92 | 9 | 85 | 7 | 3 | insufficient intervention capacity |
| Authorization | 54 | 7 | 29 | 25 | 14 | candidate capacity passes |
| Argument omission reference | 92 | 9 | 20 | 64 | 11 | already studied |

Schema drift has broad tool coverage but no observed reranking opportunity:
TF-IDF Rank-1 is environment-applicable for all 94 development targets. Timeout
has only seven correctable Rank-1 conflicts, below the prespecified development
minimum of ten; six of the seven replacement sources use `search_docs`.

Authorization is the only new family with adequate candidate capacity. Its 25
correctable conflicts span seven source tools, fourteen replacement memories,
and both retry and stop policies. No single replacement memory accounts for
more than 24% of these conflicts.

The combined number hides two different strata: released transient
authorization has 26 targets and eight correctable conflicts, while the
persistent local extension has 28 targets and seventeen correctable conflicts.

## Observable-state limitation

The normalized structural prefix separates schema drift from genuine argument
omission in this development population. In contrast, all 26 transient and all
28 persistent authorization targets fall into seven signatures shared across
the two conditions. At the first denial, the allowed observation therefore
cannot determine whether retry or stop is appropriate.

This is a property of the available observation, not a reason to expose the
benchmark's hidden recoverability label. A direct single-decision classifier
would be forced to guess within these shared states.

Critically, reaching a repeated-denial state requires retrying the persistent
authorization failure. The existing safety contract counts that retry as a
Safety Violation, and any Safety Violation invalidates Recovery Validity.
Therefore a diagnostic retry is not a valid way to resolve the ambiguity. The
evaluation contract must not be weakened to rescue the method.

## Next method step

The stateful diagnostic-retry branch is rejected. The next safe extension is a
separately disclosed evaluation of the benchmark's released transient
authorization condition, where retry is part of the released environment
semantics. Its 26 development targets contain only eight correctable Rank-1
conflicts, so no GPU run is justified yet. The next CPU step must audit the
unused public-test native-authorization cohort and stop unless it supplies at
least the frozen capacity threshold. Persistent authorization remains a
limitation rather than a claimed success.
