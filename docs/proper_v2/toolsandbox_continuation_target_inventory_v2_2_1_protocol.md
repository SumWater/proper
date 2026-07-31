# ToolSandbox continuation target inventory v2.2.1

This prospective audit scans the complete frozen ToolSandbox named-scenario
inventory without playing a scenario or loading a model.

Its purpose is to find candidates for a later CPU selector and recoverable
branch screen. It does not itself create held-out targets.

A candidate must:

- be a clean `STATE_DEPENDENCY` and `MULTIPLE_TOOL_CALL` scenario;
- have at least three native milestones, used only as a continuation-depth
  proxy;
- avoid external-tool dependencies;
- not be an exact model-exposed target;
- not be a semantic-family variant of a model-exposed target;
- not be a protected memory-source family.

Every surviving candidate remains unauthorized for model execution until a
CPU-only screen verifies:

- an observable and reproducible failed prerequisite branch;
- a safe recovery action supported by public tools;
- at least two necessary steps after recovery;
- an identifiable selector or lifecycle intervention;
- no target output has previously been read.

After that screen, candidates must be split prospectively into development,
held-out, and preservation partitions. A target used to tune a protocol cannot
later move into the held-out partition.
