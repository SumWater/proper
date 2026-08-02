# Tau3 execution-state continuation scripted screen

## Outcome

The frozen 12-pair tau3 development branch result was replayed through the
execution-state continuation layer added at commit `8610118`. The input branch
screen SHA-256 remained
`24b9967ac3790d5056f716899791469ee017400fc7a34a32d8adecb14a579eae`.
The new screen SHA-256 is
`d954248cc05814f32759b02839584378b6cfe16bbec60bcfe98356c0ee35038c`.

No source task was executed in this replay. The screen reconstructed each
complete observable ActionExecutionLedger, rejected hidden-field input at the
deserialization boundary, and consumed only previously recorded public tool
evidence. No model output was read and no GPU was used.

## Results

All 12 development-only pairs passed:

| Effect class | Pairs | Progress handoff and completion |
|---|---:|---:|
| read-only | 4 | 4/4 |
| idempotent state setting | 4 | 4/4 |
| non-idempotent side effect | 4 | 4/4 |

For every pair, the first distinct continuation observation completed the
first subgoal and routed to `continue`. The second completed the remaining
subgoal and routed to `stop` with `observable_task_complete`. All ledger effects
were resolved, all recovery repeats had already been blocked, and every
non-idempotent native action had executed once.

## Interpretation boundary

This result establishes compatibility between the frozen tau3 scripted branch
evidence and the new execution-state representation. It is not task completion
by Qwen3-8B, not a selector result, not held-out evidence, and not confirmation.
The two continuation subgoals are scripted validation contracts.

The screen authorizes designing and freezing a new tau3 development model
protocol. It does not authorize running that protocol. Before a model run, the
prompt, subgoal-construction rule, budgets, conditions, evaluator endpoints,
input hashes, base-capability gate, exclusions, and stop rules must be frozen.
