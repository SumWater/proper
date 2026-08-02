# PlanBench-XL source qualification result

## Frozen source

- repository: `https://github.com/JiayuJeff/PlanBench-XL`;
- revision: `a0dacc2d227e197a61011a68d3b15c24aebbb2a1`;
- qualification mode: read-only, CPU-only, no model, no task play;
- all 12 frozen code/data/README hashes matched the qualification contract;
- no `LICENSE` or `COPYING` file was present at repository root.
- structured qualification result SHA-256:
  `90ef60e2670cde2c1d9628f19fde14b9eca5e249338234eef3fbb181bec1d121`.

Because the source contains no redistribution license file, it was inspected
from a temporary checkout but was not vendored, bundled, or committed into
PROPER. This is a packaging/redistribution limitation, not a claim about the
paper's scientific validity.

## Structural inventory

- 327 queries and 327 task definitions;
- 56 datatypes;
- 185 baseline tools, 925 noisy tools, and 555 blocker tools, totaling 1,665;
- task paths require 5--9 tool steps;
- 185 blocker variants for each of explicit failure, implicit failure, and
  semantic-misleading conditions.

The official blocker generator was run with a frozen seed-42 structural
configuration. All 327 task plans were generated successfully. Of these, 322
contained at least one selected blocker edge and retained an alternate path;
five single-path plans selected zero blocker edges. Every retained path still
required at least five tool steps. The generated plan SHA-256 was
`a2ad0386b59744b5ddd0a285c7a96b8dab38daa60a914404d0ef87b3adefb810`.

The 322 count is a structural continuation pool, not an eligible, held-out, or
confirmatory target count. No cross-benchmark exposure exclusion, base-model
capability gate, or model behavior test has been performed.

## Decisive action-effect limitation

The frozen retail executor implements the 185 baseline tools as database
lookups and value transformations. It does not mutate the environment. The
observable action-effect inventory is therefore:

| Effect class | Tool count |
|---|---:|
| read-only | 185 |
| idempotent state setting | 0 |
| non-idempotent side effect | 0 |
| unknown | 0 |

PlanBench-XL can test long-horizon replanning after failed or misleading
read-only calls, but it cannot test the full PROPER v2.3 claim requiring
state-setting and non-idempotent side-effect safety. It must not become the
only new target source for the unified experiment.

## Decision

The source-qualification checks passed, but the full PROPER v2.3 capacity gate
stopped with accepted candidate count zero. No model or GPU run is authorized.
The stop reasons are:

1. zero state-setting and non-idempotent-side-effect coverage;
2. Qwen3-8B base capability has not been established prospectively;
3. the checked source revision contains no redistribution license file.

PlanBench-XL may remain a future continuation-only development source if its
license and base-capability issues are resolved. Such a study must report its
read-only scope separately and cannot support the complete execution-safety
claim.
