# ToolSandbox Qwen3-8B exploratory pilot results

## Frozen artifacts

- Results:
  `outputs/proper_v2/toolsandbox_model_pilot_v2_1/qwen_results.json`
- Results SHA256:
  `3ec804cb5d8e0ba98e60d36099a525210965b6fcfe1ddf9426549b938bc3f07a`
- Run log SHA256:
  `306d25be1b543c8e4a4e888ab326a2b115d6bdc53edd7ca01206060f50ef2005`
- Model: local Qwen3-8B, greedy decoding, thinking disabled
- Primary cohort: 12 behaviorally distinct paired targets
- Conditions: TF-IDF Rank-1 memory versus PROPER v2.1 memory
- Model decisions: 87/87 valid JSON
- Pair starts: 12/12 identical across conditions

The pilot was capacity-selected and exploratory. It is not a confirmatory test
and does not authorize a claim about all Agent-memory settings.

## Phase-stratified results

| Phase | Pairs | TF-IDF mean similarity | PROPER mean similarity | Better / worse / tie |
|---|---:|---:|---:|---:|
| `pre_action` | 3 | 0.0000 | 1.0000 | 3 / 0 / 0 |
| `post_failure` | 9 | 0.4296 | 0.4296 | 0 / 0 / 9 |

The pooled descriptive mean was 0.3222 for TF-IDF and 0.5722 for PROPER,
with 3 positive, 0 negative, and 9 tied pairs. The pooled value must not be
used to hide the phase interaction.

## Diagnostics

| Diagnostic | TF-IDF | PROPER |
|---|---:|---:|
| `pre_action` first-decision alignment | 0 / 3 | 3 / 3 |
| `pre_action` minefield conditions | 3 / 3 | 0 / 3 |
| `post_failure` first-decision alignment | 7 / 9 | 9 / 9 |
| `post_failure` tool exceptions | 9 | 24 |
| `post_failure` repeated identical calls | 8 | 21 |

In all three insufficient-information targets, the PROPER-selected stop memory
caused Qwen to stop safely on the first decision. TF-IDF caused guessed or
unsafe calls, triggered every native minefield, and scored zero.

In the nine prerequisite-recovery targets, PROPER improved the first recovery
decision from 7/9 to 9/9, but did not improve final ToolSandbox similarity.
The selected action card remained injected after it had succeeded. Qwen often
repeated `set_wifi_status`, `set_cellular_service_status`, or
`set_low_battery_mode_status` instead of consuming the prerequisite and
returning to task planning. This produced more exceptions and repeated calls
than TF-IDF and left every pair tied.

## Conclusion

PROPER v2.1 shows positive transfer across benchmark and policy type for
`pre_action` safety decisions. It also improves immediate action selection for
`post_failure` prerequisite recovery, but the present memory-use protocol does
not support successful multi-step continuation. Therefore the result supports
phase-aware selective applicability, not unified end-to-end generalization.

The next development version should add an explicit memory lifecycle:

1. apply a recovery card only while its trigger remains active;
2. verify its success evidence after execution;
3. mark the card consumed when the recovery target is satisfied;
4. remove or demote the consumed action from subsequent prompts;
5. resume ordinary task planning with the updated visible state;
6. stop if the card's stop condition or retry budget is reached.

This should be developed as PROPER v2.2. The existing v2.1 cohort and outputs
must remain frozen; any v2.2 run on these targets is development evidence and
requires a new held-out cohort for later validation.
