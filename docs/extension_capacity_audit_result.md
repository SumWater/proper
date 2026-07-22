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

## Observable-state limitation

The normalized structural prefix separates schema drift from genuine argument
omission in this development population. In contrast, all 26 transient and all
28 persistent authorization targets fall into seven signatures shared across
the two conditions. At the first denial, the allowed observation therefore
cannot determine whether retry or stop is appropriate.

This is a property of the available observation, not a reason to expose the
benchmark's hidden recoverability label. A direct single-decision classifier
would be forced to guess within these shared states.

## Next method step

PROPER v2 should be designed as a state-aware conservative gate:

1. on the first authorization denial, permit at most one diagnostic retry;
2. if the same call succeeds, no further recovery memory is needed;
3. if the same denial recurs, use the now-observable repeated-failure state to
   select a stop-and-report memory;
4. retain the existing argument-repair branch;
5. treat schema drift and timeout primarily as preservation strata unless a new
   memory bank or dataset creates sufficient Rank-1 conflicts.

The next stage is protocol and CPU implementation for this two-decision
authorization branch. No new model outputs should be generated before its
development/evaluation split, prompt, metrics, and stopping rules are frozen.
