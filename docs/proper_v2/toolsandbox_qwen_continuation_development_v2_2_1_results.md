# ToolSandbox Qwen3-8B continuation development results

## Status and artifact identity

This is a development result on the 12 model-exposed v2.1 pairs. It is not a
confirmatory or held-out result and does not authorize a claim about general
Agent memory settings.

- result:
  `outputs/proper_v2/toolsandbox_qwen_continuation_development_v2_2_1/results.json`
- result SHA-256:
  `541f764abb25f6719f633b8189d87e3b6177825db42087725efc5d32518fc6e8`
- frozen run-config SHA-256:
  `e898f2d8fa0837ac817e3bece6aeb62ca7fdf5f9c50b83971629607085da6686`
- prepared four-condition manifest SHA-256:
  `3efcd90ee2e8b30685430326c1d1781caec15c35c6fd8ee28dfd066e13c89f21`
- prospective inventory SHA-256:
  `a969e50b35671bbba3641c7a33640c7e7ca5a452a608536612546c94808a48b9`
- smoke passed / full development completed: yes / yes
- pairs / conditions: 12 / 48
- valid model JSON requests: 175 / 175
- identical four-condition starts: 12 / 12
- frozen-input hash matches: 17 / 17

An independent recount from the raw records found 175 unique model-attempt
request IDs and 175 unique request-log IDs, with matching request hashes and
token counts. Accepted tool decisions match the serialized tool histories in
all 48 conditions. The frozen v2.1 and v2.2 result hashes remain unchanged.

The one-shot entry executed scripted dynamic validation in the Qwen runner's
process and embedded its summary in this result. It did not serialize a
standalone `dynamic_validation.json`; consequently, the embedded summary is
auditable, but the full scripted dynamic records were not retained as a
separate artifact.

## Endpoint-separated results

### Selector first step

The selector is inherited from v2.1. These are same-pair development
observations, not new held-out selector evidence.

| Phase | TF-IDF alignment | PROPER alignment | Similarity comparison |
|---|---:|---:|---|
| pre-action | 0/3 | 3/3 | PROPER better 3, tie 0, worse 0 |
| post-failure | 6/9 | 9/9 | tie 9 |

The pre-action selector interaction is reproduced. In post-failure cases,
PROPER improves first-step policy alignment but not final similarity under
persistent injection.

### Memory lifecycle

All 9 post-failure lifecycle conditions transitioned from `active` to
`consumed` after success evidence and handed planning back to the ordinary
task prompt. The actionable memory was removed after consumption.

Prompt-only lifecycle, compared with persistent PROPER memory:

- mean similarity increased from 0.4296 to 0.4963;
- it was better on 3 pairs and tied on 6;
- tool exceptions decreased from 25 to 15;
- executed identical repeats decreased from 23 to 11;
- final task completion remained 0/9.

Consumption and prompt handoff therefore work as lifecycle mechanisms, but
prompt removal alone does not reliably prevent the model from repeating an
action already visible in trajectory context.

### Continuation controller

The replan controller blocked 10 exact proposals to repeat a successfully
consumed prerequisite. Every blocked attempt received a subsequent valid
accepted decision, and no replan budget was exhausted. Across all 9
post-failure pairs, the consumed prerequisite appears exactly once in the
executed tool history.

Compared with prompt-only lifecycle:

- mean similarity increased from 0.4963 to 0.6815;
- the controller condition was better on 6 pairs and tied on 3;
- tool exceptions decreased from 15 to 1;
- executed identical repeats decreased from 11 to 8;
- final task completion remained 0/9.

This establishes a narrow controller effect: exact repeats of the consumed
recovery action were prevented and replanning continued. It does not establish
general multi-step action deduplication.

### Final task completion

| Phase | Condition | Mean similarity | Complete |
|---|---|---:|---:|
| pre-action | TF-IDF persistent | 0.0000 | 0/3 |
| pre-action | PROPER persistent | 1.0000 | 3/3 |
| pre-action | lifecycle prompt-only | 1.0000 | 3/3 |
| pre-action | lifecycle + replan controller | 1.0000 | 3/3 |
| post-failure | TF-IDF persistent | 0.4296 | 0/9 |
| post-failure | PROPER persistent | 0.4296 | 0/9 |
| post-failure | lifecycle prompt-only | 0.4963 | 0/9 |
| post-failure | lifecycle + replan controller | 0.6815 | 0/9 |

The controller improves partial milestone progress, but none of the 9
post-failure tasks completes. Final-task continuation remains unsolved.

### Safety

| Phase | Condition | Minefield conditions | Tool exceptions | Executed identical repeats |
|---|---|---:|---:|---:|
| pre-action | TF-IDF persistent | 3 | 3 | 8 |
| pre-action | PROPER persistent | 0 | 0 | 0 |
| pre-action | lifecycle prompt-only | 0 | 0 | 0 |
| pre-action | lifecycle + replan controller | 0 | 0 | 0 |
| post-failure | TF-IDF persistent | 0 | 11 | 10 |
| post-failure | PROPER persistent | 0 | 25 | 23 |
| post-failure | lifecycle prompt-only | 0 | 15 | 11 |
| post-failure | lifecycle + replan controller | 0 | 1 | 8 |

The 8 controller-condition repeats are not repeats of the consumed recovery
action. They are later ordinary-task actions: two repeated holiday searches,
four duplicate message sends, one repeated `end_conversation`, and one
repeated location-service action. In particular, four duplicate message sends
show that a zero minefield count is not sufficient evidence of safe
continuation. The current execution ledger protects only the consumed memory
action, not every successful or side-effecting task action.

Therefore v2.2.1 improves recovery-action safety but does not solve overall
trajectory safety.

### Cost

| Phase | Condition | Model requests | Tool calls | Prompt tokens | Completion tokens | Total tokens |
|---|---|---:|---:|---:|---:|---:|
| pre-action | TF-IDF persistent | 12 | 12 | 11,196 | 521 | 11,717 |
| pre-action | PROPER persistent | 3 | 0 | 2,489 | 92 | 2,581 |
| pre-action | lifecycle prompt-only | 3 | 0 | 3,087 | 86 | 3,173 |
| pre-action | lifecycle + replan controller | 3 | 0 | 3,087 | 86 | 3,173 |
| post-failure | TF-IDF persistent | 36 | 36 | 32,816 | 735 | 33,551 |
| post-failure | PROPER persistent | 36 | 36 | 31,695 | 728 | 32,423 |
| post-failure | lifecycle prompt-only | 36 | 36 | 35,840 | 809 | 36,649 |
| post-failure | lifecycle + replan controller | 46 | 36 | 48,854 | 1,184 | 50,038 |

Blocked attempts are included in cost. Relative to prompt-only lifecycle in
post-failure cases, the controller uses 27.8% more model requests and 36.5%
more total tokens, while executing the same number of tool calls. These are
token and operation counts, not latency, energy, or monetary-cost measures.

## Prospective target inventory

The no-play inventory audited 1,032 unique ToolSandbox scenario names without
loading a model, reading model outputs, or playing a scenario. It found zero
eligible candidates:

- 983 lacked the required category/depth proxy;
- 11 required external tools;
- 12 belonged to a memory-source family;
- 12 were already model-exposed targets;
- 14 were variants of model-exposed semantic families.

Thus the current bundled ToolSandbox inventory cannot supply a new
confirmatory continuation cohort under the frozen exclusion rules. Inventory
alone authorizes neither a model run nor a held-out claim. A later
confirmatory stage requires genuinely unexposed targets acquired outside this
exhausted pool, followed by a frozen CPU selector and recoverable-branch
screen before any model execution.

## Development conclusion

v2.2.1 fixes the specific failure it was designed to address: after verified
consumption, exact recovery-action repeats are blocked and the model is
replanned instead of immediately stopped. This improves partial progress and
substantially reduces tool exceptions.

It does not solve final task completion or general continuation safety. The
ordinary-task execution ledger is incomplete, later side-effecting actions can
still repeat, and post-failure completion is 0/9. The frozen v2.2.1 protocol,
config, runner, and result must not be modified after these observations and
then relabeled as confirmatory evidence. Any broader action-ledger design must
receive a new version and remain development-only until new unexposed target
capacity exists.
