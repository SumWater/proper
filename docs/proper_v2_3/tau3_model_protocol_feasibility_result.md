# tau3 model protocol feasibility gate

## Outcome

The CPU-only gate stops before freezing or implementing a tau3 model runner.
All 12 development candidates still map to the pinned source tasks and guarded
actions, but only the four `pre_action` read-only candidates have a defensible
model start using the public task opening alone.  The eight `post_failure`
candidates do not yet have frozen public conversation histories, matching
environment initializations, public failure receipts, or identical-start replay
proofs.

The earlier scripted branch and continuation screens remain valid controller
regressions.  They do not constitute executable full-task model branches.

## Why the stop is necessary

The source task `evaluation_criteria.actions` describes evaluator targets, not a
complete public trajectory.  Several selected state-setting and side-effect
actions require identifiers, addresses, confirmations, or prior tool results
that are not present at task start.  Synthesizing those prefixes directly from
gold actions would leak evaluator information into branch construction and
would not demonstrate that all conditions received a naturally obtainable,
identical observable state.

The official half-duplex orchestrator can resume from
`initial_state.message_history`, so the runtime is not the blocker.  The missing
scientific artifact is a public branch capture with a corresponding environment
snapshot.

## Frozen interpretation

- Partition: development only; never held-out or confirmatory.
- Source action mappings: 12/12.
- Model-ready public starts: 4/12, all `pre_action` and read-only.
- Model-ready `post_failure` starts: 0/8.
- New held-out capacity: 0.
- Model protocol freeze: not authorized.
- Model runner implementation and GPU run: not authorized.

## Next admissible gate

Design a CPU-only public branch capture mechanism.  It must obtain the prefix
through public user messages and native tool results, persist both public
message history and environment initialization, inject only an observable
failure or unknown-result receipt, and replay an identical start across all
conditions.  It must not use task IDs, future gold actions, recoverability
labels, or evaluator outcomes as method inputs.
