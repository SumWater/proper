# PROPER v2.2 unconsumed-target CPU capacity results

## Boundary

The audit inspected two public target inputs and the frozen memory bank. It
read no target model outputs, played no scenario, loaded no model, and used no
GPU. The result is capacity evidence only.

## Result

| Endpoint | Result |
|---|---:|
| Targets audited | 2 |
| V2.1 model-exposed targets | 0 |
| Exact source-family overlaps | 0 |
| Independent semantic families | 1 |
| Behaviorally distinct TF-IDF/PROPER pairs | 0 |
| PROPER-selected safe-stop policies | 2 / 2 |
| Lifecycle tool-call guards safe | 2 / 2 |
| Selected memories with target-specific trigger match | 0 / 2 |

For both variants, TF-IDF Rank-1 was already
`toolsandbox::remove_contact_without_search::stop`. PROPER preserved the same
memory and the same `stop_and_report` intervention. The pairs therefore cannot
identify a selector or lifecycle effect.

The stop behavior is conservative, but the selected memory's specific trigger
is missing lookup capability. The targets instead lack the contact-removal
execution capability. The memories match only the generic
`failure_state:insufficient_information` evidence. A model could stop safely
while reporting the wrong reason.

## Decision

The two records are preservation-only development inputs:

- `development_model_output_holdout_ready=false`;
- `confirmatory_capacity_ready=false`;
- no model run should be performed on these targets.

This null capacity result must not be repaired by adding a target-specific
memory and then reusing the same targets as held-out evidence. Any selector
change motivated by this audit makes these inputs development data.

The frozen 12-pair Qwen lifecycle run remains permissible as development work.
New independently sourced targets are required for later held-out validation.
