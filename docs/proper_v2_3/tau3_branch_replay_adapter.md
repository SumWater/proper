# tau3 split-state branch replay adapter

The CPU-only adapter implements the runtime boundary required by the public
branch capture design. It wraps an environment instead of modifying frozen
tau2/tau3 source files.

When the orchestrator initializes a branch, the adapter verifies the complete
participant-visible history against the frozen start, restores the complete
evaluator-side checkpoint, and passes an empty mutation history to the wrapped
environment. It rejects task initialization data or actions, checkpoint/hash
mismatches, participant-history changes, restored-state mismatches, and a
second initialization attempt.

Tau-specific imports are lazy. Local unit tests use a fake environment and
prove that a checkpoint containing one already-sent non-idempotent effect is
restored with zero replayed mutations. The next gate is a native tau3 CPU smoke
on the remote machine with the pinned environment revision. That smoke may use
an isolated in-memory database copy but must not run a model, expose one of the
12 tasks to a model, construct real branches, or use a GPU.

Passing local adapter tests does not create the eight missing post-failure
branches and does not authorize a model protocol or model runner.

The frozen remote entry point is
`experiments/proper_v2_3/run_tau3_branch_replay_native_smoke_remote_v2_3.py`.
It dynamically chooses the lexicographically first pending order from a fresh
in-memory retail database, executes `cancel_pending_order` exactly once, marks
its public result unknown, restores the post-action checkpoint into a second
fresh environment, and verifies the restored cancelled state without replaying
the call. It loads no benchmark task and uses no model or GPU.

The first remote attempt stopped at the protocol-v1 Python 3.12 guard while the
active environment was Python 3.11.15. It occurred before tau3 import and
before any native action. Protocol v2 permits Python 3.11 or 3.12, matching the
repository's pre-existing frozen tau3 source-checkout execution contract. This
is an infrastructure correction only; adapter logic and pass criteria are
unchanged.

The protocol-v2 retry next stopped because importing tau2's top-level package
eagerly imports the unused batch runner and therefore `pandas`. Protocol v3
loads the pinned tau2 source as a lightweight namespace and imports only the
retail domain, data-model, and environment modules used by the smoke. This
avoids expanding the isolated environment with unrelated runner dependencies.
The v2 attempt stopped before environment construction and native execution;
method logic and pass criteria again remain unchanged.
