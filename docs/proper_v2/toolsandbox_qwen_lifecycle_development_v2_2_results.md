# ToolSandbox Qwen3-8B lifecycle development results

## Status and artifact identity

This is a development result on the 12 model-exposed v2.1 pairs. It is not a
confirmatory or held-out result and does not authorize a claim about general
Agent memory settings.

- result:
  `outputs/proper_v2/toolsandbox_qwen_lifecycle_development_v2_2/results.json`
- result SHA-256:
  `de84767fc3136e1832210d5c1692a12302f3b1551e1efbb4a7cafcc889dd83a1`
- frozen run-config SHA-256:
  `1765b24c7eeb72b95628c7afadb9857d5c7466e92cd44329a262d0b3c76dbac7`
- run completed: yes
- smoke passed: yes
- pairs / conditions: 12 / 24
- valid model JSON decisions: 79 / 79
- identical paired starts: 12 / 12

Every frozen-input hash recorded by the result matches the corresponding
local file. The result contains 79 unique request IDs, matching both the model
request-log length and the independently counted decision length.

The serialized condition key `proper_v2_1_memory` is retained internally for
compatibility with the v2.1 runner. In this result it denotes the PROPER v2.2
lifecycle condition, as shown by its per-decision lifecycle and controller
records. It must not be interpreted as a rerun of the v2.1 injection policy.

## Endpoint-separated results

### Selector first step

The selector itself was inherited from v2.1; this run does not provide new
held-out selector evidence.

- pre-action alignment: TF-IDF 0/3; PROPER v2.2 3/3
- post-failure alignment: TF-IDF 7/9; PROPER v2.2 9/9

These development-pair observations reproduce the earlier first-step
interaction. They do not isolate a new selector effect.

### Memory lifecycle

The scripted same-process check passed:

- post-failure memory consumed after one prerequisite call: 9/9
- ordinary-planning prompt handoff after consumption: 9/9
- pre-action stopped: 3/3
- scripted repeated memory actions / tool exceptions: 0 / 0

The Qwen trajectories confirm the state transition but expose an important
continuation limitation:

- all 9 post-failure trajectories changed from `active` to `consumed`;
- all 9 then received the ordinary-task-planning prompt with the actionable
  memory removed;
- in 6/9 trajectories, Qwen nevertheless proposed the consumed prerequisite
  again;
- all 6 proposals were blocked by the controller, which converted the
  decision to a stop.

Therefore, memory consumption and prompt handoff worked, but autonomous
multi-step continuation was not solved. The absence of executed repeated
calls depends on the controller in six trajectories.

### Final task completion

| Phase | Condition | Mean similarity | Complete |
|---|---|---:|---:|
| pre-action | TF-IDF | 0.0000 | 0/3 |
| pre-action | PROPER v2.2 | 1.0000 | 3/3 |
| post-failure | TF-IDF | 0.4296 | 0/9 |
| post-failure | PROPER v2.2 | 0.5455 | 0/9 |

For post-failure similarity, PROPER v2.2 was better on 7 pairs, tied on 2,
and worse on 0. This is partial-progress evidence only: neither condition
completed any of the 9 post-failure tasks.

The three holiday trajectories proceeded beyond the prerequisite without a
guard block, but still failed the dynamic-reference and dependent-final-answer
diagnostics. The other six post-failure trajectories stopped when the
controller blocked a consumed-action repeat.

### Safety

| Phase | Condition | Minefield conditions | Tool exceptions | Executed identical repeats |
|---|---|---:|---:|---:|
| pre-action | TF-IDF | 3 | 2 | 6 |
| pre-action | PROPER v2.2 | 0 | 0 | 0 |
| post-failure | TF-IDF | 0 | 10 | 7 |
| post-failure | PROPER v2.2 | 0 | 0 | 0 |

The same-run TF-IDF post-failure counts differ slightly from the frozen v2.1
run (10 versus 9 exceptions; 7 versus 8 repeats), while its mean similarity
and first-step alignment are unchanged. Comparisons above therefore use the
paired baseline from this v2.2 run.

PROPER v2.2 executed no minefield action, exception-producing action, or
identical repeat in this development run. This safety result includes six
controller interventions and must not be described as model-only compliance.

### Cost

| Phase | Condition | Model decisions | Tool calls | Prompt tokens | Completion tokens |
|---|---|---:|---:|---:|---:|
| pre-action | TF-IDF | 12 | 12 | 11,106 | 498 |
| pre-action | PROPER v2.2 | 3 | 0 | 3,090 | 86 |
| post-failure | TF-IDF | 36 | 36 | 32,776 | 733 |
| post-failure | PROPER v2.2 | 28 | 22 | 28,094 | 675 |

Within post-failure trajectories, PROPER v2.2 used 22.2% fewer model
decisions, 38.9% fewer executed tool calls, 14.3% fewer prompt tokens, and
7.9% fewer completion tokens than the paired TF-IDF condition. Across both
phases, the reductions were respectively 35.4%, 54.2%, 28.9%, and 38.2%.

These are local-model token counts and trajectory operation counts, not
latency, energy, or monetary-cost measurements. Some reductions result from
controller-induced early stopping, so they cannot be interpreted independently
of the zero post-failure completion rate.

## Development conclusion

The v2.2 lifecycle fixes the original execution-level pathology: a successful
prerequisite is consumed, its actionable memory is removed, and the same tool
call is not executed repeatedly. It does not yet establish successful return
to the original task. Qwen still proposes the completed prerequisite in 6/9
post-failure trajectories, and final completion remains 0/9.

The frozen v2.2 protocol and runner must not be tuned after observing these
outputs and then reused as a confirmatory protocol. Any change intended to
improve continuation requires a new explicitly versioned development contract
and new target capacity; the two previously audited unconsumed targets remain
preservation-only and are not suitable for that purpose.
