# PROPER v2.3 five-condition Qwen development result

## Frozen identity and boundary

- remote run: `20260801T122152Z-amax-0044e8fd6417`;
- remote revision: `0044e8fd64177ddcbe3301bd44b639dea0e8140c`;
- `results.json` SHA-256:
  `3853d82e4ac048e2821cbb06185ffe6b2ee8e58f52445f234176fc2733bcbe60`;
- 12 existing model-exposed development pairs, 60 conditions;
- Qwen3-8B, deterministic local inference, 224 model requests;
- GPU smoke passed and the complete development run finished;
- this is not held-out or confirmatory evidence.

The prespecified stage gate failed only because post-failure completion was not
strictly better than condition four. This negative result is frozen without
retuning or rerunning the same protocol.

## Endpoint-separated findings

### Selector

All four PROPER conditions had aligned first decisions on 9/9 post-failure and
3/3 pre-action pairs. TF-IDF aligned on 7/9 post-failure and 0/3 pre-action
pairs. This retains the earlier selector first-step effect; it does not imply
final completion.

### Memory lifecycle

The fifth condition executed one successful recovery action on every
post-failure pair (9/9). Controller records show consumed-state ordinary-task
handoff on all 9 pairs. Final controller states are not lifecycle-consumption
counts: 7 of those trajectories later stopped after bounded interventions,
while 2 remained consumed at the end; the 3 pre-action pairs stopped safely.

### Recovery continuation

The fifth condition recorded 25 blocked ledger proposals. Eighteen produced a
model feedback/replan attempt and seven were terminal blocks after budget
exhaustion. The blocked reasons were:

- 21 successful-action repeat blocks: 14 idempotent state settings and 7
  read-only actions;
- 4 unsafe or unproven non-idempotent retries.

All allowed ledger executions were resolved. No verification action was needed
and no outcome-unknown action occurred in this cohort.

### Final task completion

All five conditions completed 0/9 post-failure tasks. The post-failure mean
ToolSandbox similarities were:

| Condition | Mean similarity | Completed |
|---|---:|---:|
| TF-IDF persistent | 0.4296 | 0/9 |
| PROPER persistent | 0.4296 | 0/9 |
| lifecycle prompt-only | 0.4963 | 0/9 |
| v2.2.1 recovery-action controller | 0.6815 | 0/9 |
| v2.3 full-ledger controller | 0.5233 | 0/9 |

Thus v2.3 did not improve completion and reduced partial progress relative to
condition four. On pre-action pairs, all four PROPER conditions completed 3/3
with similarity 1.0; TF-IDF completed 0/3 and hit all 3 minefields.

### Safety

The fifth condition executed zero identical post-branch action repeats,
compared with 8 under condition four. Duplicate non-idempotent side-effect
executions were zero. Four non-idempotent repeat/retry proposals were blocked.
The two ledger-classified read-only repeat executions followed prior failed
attempts rather than prior successful actions. The fifth condition had zero
minefields and zero post-failure tool exceptions.

### Cost

For the 9 post-failure pairs, condition four and condition five each made 46
model requests. Condition five made 21 native tool calls versus 36, but used
73,515 prompt tokens versus 48,834. Its total prompt-plus-completion tokens were
74,661 versus 50,018, an increase of 49.3%. It used 18 feedback replans versus
10 for condition four.

## Interpretation and stop decision

The supported v2.3 finding is narrower than the research target: a complete
observable action ledger prevented successful-action repetition and removed
duplicate non-idempotent effects, but bounded replanning did not produce final
post-failure completion and increased token cost. The result does not weaken
the two confirmatory PROPER v1 findings.

Per the frozen rule, development on these 12 pairs stops here. No prompt,
budget, taxonomy, or controller tuning on this result may be relabelled as
confirmatory. Further model experimentation requires genuinely unconsumed
targets and a new prospectively frozen protocol; current audited capacity is
zero.
