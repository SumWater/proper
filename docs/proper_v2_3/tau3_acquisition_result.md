# Stopped tau3 acquisition result

## Status

The one authorized clean-worktree acquisition invocation reached the model and
tau3 runtime at remote project revision
`8fd7c469ec70d8c406828903d83a0999470d2a5a`. It stopped on the fifth ordered
pair with `invalid_user_output`. The returned artifacts are preserved exactly;
the run must not be resumed, rerun, or replaced.

The first four `pre_action` branches were captured. The fifth pair reached a
`post_failure` target, executed one read-only lookup, received `User not
found`, and then stopped because the next user-model response was natural
language rather than the required single strict JSON object. The runtime's
zero-retry rule was followed. Therefore the frozen acquisition yield is 4/12
overall and 0/8 for `post_failure`.

## Endpoint-separated interpretation

- Selector: not measured; this was memory-acquisition infrastructure, not a
  selector comparison.
- Lifecycle: not measured; no acquired post-failure branch reached lifecycle
  evaluation.
- Recovery continuation: not measured; zero post-failure branches were
  captured.
- Final task completion: not measured.
- Safety: no target state-changing action and no non-idempotent side effect was
  executed. The only native tool execution was a failed read-only lookup.
  Duplicate non-idempotent executions were zero. This is a narrow execution
  fact from the partial acquisition, not general safety evidence.
- Cost: the returned aggregate reports seven model requests, 11,366 prompt
  tokens, and 444 completion tokens. Independent recomputation from all
  preserved worker records finds eight requests, 12,040 prompt tokens, and 483
  completion tokens. The invalid user response was omitted from the aggregate:
  one request, 674 prompt tokens, and 39 completion tokens. Both figures are
  retained; the returned aggregate is not silently corrected.

## Scientific disposition

This is a preserved negative development result. It did not create the frozen
12-branch acquisition cohort and does not authorize a five-condition model
comparison. It provides no held-out or confirmatory evidence and does not
alter any PROPER v1 conclusion.

No prompt, parser, retry policy, runner, pair order, or budget may be modified
and rerun on this same cohort under the frozen protocol. Any future acquisition
work would require a new prospective protocol and genuinely new authorization;
the current tau3 acquisition line stops here.

`validate_tau3_acquisition_result_v2_3.py` verifies all returned hashes and
sizes, frozen input hashes, the exact stopping trace, the safety boundary, and
the raw-record cost reconciliation. A passing local freeze validation means
only that this stopped result was preserved and audited correctly;
`scientific_stage_passed` remains false.
