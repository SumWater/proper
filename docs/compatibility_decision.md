# ToolMisuseBench compatibility decision

Decision: **PASS WITH ADAPTER AND DETERMINISTIC PREFIX REPLAY**

This decision permits the bounded memory-feasibility pilot. It does not approve large-scale/model/GPU experiments and does not claim that unmodified ToolMisuseBench provides every required condition.

## Frozen identities

- Code commit: `b6ee3412f98d2058ee487e182a72b26c58046d51`
- Code tree: `ce6663afa7f7df21e878bbde80764b77aeb80bd0`
- Dataset revision: `98eb28718b0393e029088ce80604c48807216de4`
- Dataset release: `v0.2_large`
- v0.2 manifest SHA-256: `dbc940b8ead00071b8287d301384091077158f4296fd330c36ba022b6fa93c0d`
- Verified dev split: 900 tasks, 1,249,342 bytes, SHA-256 `a5a2b49b28c66f01bdbac37966c00cca9c6a1027a6d4b5b3a8c1d1d359db27e3`

## Audit answers

| Question | Decision | Evidence/condition |
|---|---|---|
| Code/data compatible? | Conditional pass | Frozen code loads all 900 v0.2 dev tasks. Full CLI incorrectly claims Python 3.10 support; require Python 3.11+. |
| Deterministic replay? | Pass | Three-run selected-fault traces and prefix probes match; sanitized 900-task runs have zero replay differences and identical Windows/WSL aggregate hash. |
| Snapshot branching? | Fail | `snapshot()` returns only business state and has no restore. Use deterministic reset plus action-prefix replay. |
| Agent-visible fields known? | Pass with adapter | Top-level Observation is narrow, but raw post-fault details expose injection metadata. |
| Hidden-field isolation? | Raw fail; adapter pass | External sanitizer produced zero remaining injection-key leaks over 900 dev tasks. |
| Recovery Validity independently evaluable? | Pass | Structured policies/contracts and deterministic independent evaluator operate without changing official success. |
| Correct Stop independently evaluable? | Pass with wrapper | Official runner has no reason code; boundary/structured-stop layer records and evaluates it externally. |

## Mandatory instrumentation

1. Sanitize only injection-only metadata (`faults`, adversarial `original_error_code`) at the Agent observation boundary; retain ordinary tool feedback.
2. Record the action returned by the Agent before the environment transforms it.
3. Keep the raw environment trace evaluator-visible and the sanitized observation Agent-visible.
4. Recreate branches by resetting the frozen task and replaying a canonical action prefix.
5. Compute Recovery Contract metrics as a separate layer and retain official Task Success unchanged.

The 900-task adapter gate found zero sanitized replay failures, zero remaining injection leaks, and zero official episode-result differences. It found 153 Agent/official-trace action mismatches, exactly the number of schema-drift tasks, confirming that official transcripts cannot be used alone for behavior matching.

## Important semantic limitations

- Released v0.2 authz is transient: the first matching call is denied and the next identical call succeeds. None of the 144 dev authz tasks is persistent. Persistent denial is therefore a clearly labeled local extension.
- The persistent extension deterministically denies repeated calls; `stop_and_report(persistent_authorization_denial)` passes the independent contract, while retrying violates the no-post-denial-call invariant. Official Task Success is unchanged by this evaluation.
- v0.2 schema drift mutates the Agent's valid arguments on the first call only. For the audited task, the Agent returned `id`, the environment recorded transformed `account_id`, and the same original action would succeed on a second call. This is a one-shot backend mutation, not permanent interface drift. Provenance and boundary action capture are essential when labeling recovery-policy applicability.

## Python finding

Upstream declares Python `>=3.10` but imports `datetime.UTC`, which requires Python 3.11+. Five modules fail collection on Python 3.10.12. With an audit-only UTC alias, all 39 upstream tests pass on WSL; without source modification, Python 3.12 Windows collected the suite with 38 passes and one sandbox-specific atomic-replace permission failure. Formal Linux experiments must use and freeze Python 3.11+; the UTC shim is diagnostic only.

## Stop conditions carried forward

Stop the memory pilot if source-blind retrieval rarely selects/exposes inapplicable experience, if behavior following cannot be matched from boundary actions, if paired harm versus No Memory is absent/unstable, or if Oracle Provenance does not improve over source-blind retrieval. Do not implement Predicted Provenance Gate before oracle headroom is established.

