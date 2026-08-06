# AppWorld static API inventory implementation

The local implementation parses every supplied `.py` and `.pyi` member with
the standard AST and never imports or executes protected modules. Public
top-level and class callables are registered only after every source parses.
Private helpers remain available for transitive effect propagation but are not
emitted as candidates.

Each candidate record contains only hashes, signature shape, decorator count,
standard evidence codes, a preliminary effect class, and retry safety. Names,
paths, arguments, docstrings, and source are excluded. Ambiguous internal
resolution, external calls, dynamic dispatch, unproven mutation receivers, and
unproven replacement values become `unknown_effect`.

Synthetic tests cover pure reads, deterministic persistent replacement,
persistent cardinality change, external and mutation-receiver ambiguity,
private-helper propagation, syntax/encoding failures, complete multi-file
parsing, privacy, determinism, and empty input. No real bundle was decrypted.

This stage authorizes implementation of a guarded real-bundle runner only. It
does not authorize the real static inventory, target selection, task access,
model execution, GPU use, or scientific claims.
