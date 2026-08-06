# AppWorld in-memory static API inventory protocol

This design uses only the exact frozen apps bundle. Every `.py` and `.pyi`
member is parsed in memory with the standard Python AST; modules are never
imported. All public top-level and class callables form a conservative superset
before any target selection.

Classification uses observable syntax, call-graph, assignment, mutation, and
control-flow evidence. Read-only and idempotent labels require positive proof.
Cardinality changes, deletion, emission, communication, or irreversible calls
are non-idempotent. Any unresolved call, alias, dispatch, reflection, parse
ambiguity, or conflicting proof becomes `unknown_effect`, which blocks a full
capacity claim.

Outputs may contain only symbol/path/signature/content hashes, standardized
evidence codes, aggregate counts, and preliminary effect/retry labels. They may
not contain protected names, paths, argument names, docstrings, snippets, or
source bytes. Static labels do not become runtime contracts without observable
execution evidence.

Tests bundle, data, tasks, evaluator state, module imports, network, native
actions, model execution, GPU use, target selection, held-out claims, and
confirmatory claims remain forbidden. This stage authorizes implementation and
synthetic validation only; it does not authorize another real decryption.
