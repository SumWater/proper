# PlanBench-XL capacity-audit design for PROPER v2.3

## Current disposition

PlanBench-XL is registered as a prospective source, not as an accepted target
set. This local stage does not download its repository or data, execute a
scenario, read a model output, or authorize GPU use. Until a source revision
and all input hashes are frozen, the disposition remains
`stop_before_inventory`.

The source is relevant because it exposes long-horizon tool composition and
explicit, implicit, and misleading blocking conditions. Its public project
reports 327 queries and 1,665 tools. Those counts are expectations to verify
against a future frozen local source, not locally reproduced facts.

## Qualification sequence

1. Acquire the repository and dataset once, record immutable revision and file
   hashes, and retain the original license and source metadata.
2. Perform a structural inventory without a model and without playing tasks.
3. Exclude exact prior exposure, related variants of the 12 development pairs,
   memory-source families, and any task used while changing the protocol.
4. Use scripted state transitions to verify that an observable failure occurs,
   a recovery route remains possible, at least two steps remain after recovery,
   and public verification is available.
5. Freeze development, held-out, and preservation partitions before reading
   model outputs.
6. Run a separately frozen base-capability gate. Targets that Qwen3-8B cannot
   solve without the failure intervention cannot identify a recovery-memory
   effect and must not proceed to the costly comparison.

## Gold-field separation

Correct answers, golden tool paths, blocking annotations, completion labels,
and semantic-family annotations are audit/evaluation-only. They may determine
exclusion or scoring after a trajectory, but must never enter the PROPER
selector, lifecycle, ledger, progress state, prompt, or controller decision.

## Required reporting

Report the raw inventory, structurally eligible, scripted-recoverable,
base-capable, and behaviorally identifiable counts separately. Also report
action-effect coverage and every exclusion reason. Do not call the source
held-out until partitions and hashes are frozen before model exposure.

If there are fewer than 12 behaviorally distinct pairs, insufficient
action-effect coverage, or a Qwen3-8B base-capability floor, stop rather than
selecting cases based on observed intervention performance.
