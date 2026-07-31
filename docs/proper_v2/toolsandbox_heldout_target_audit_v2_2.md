# PROPER v2.2 ToolSandbox held-out target audit

This is an input-only audit. It reads no model outputs and plays no target
scenario.

The frozen 31-scenario inventory partitions as follows:

- 12 scenarios were exposed to Qwen in the v2.1 development pilot;
- 10 otherwise unconsumed scenarios overlap semantic families used to create
  the current memory bank;
- 7 scenarios were capacity-screened but have no behaviorally distinct
  selector intervention and are preservation-only;
- 2 scenarios from one non-source semantic family are unconsumed and require a
  new CPU-only capacity screen;
- 0 scenarios are currently eligible for a held-out lifecycle-effect test.

The seven preservation records may later test gross regressions, but they
cannot identify a lifecycle effect because the compared interventions are
behaviorally identical.

The present inventory therefore does not authorize a confirmatory v2.2 run.
The two unconsumed non-source targets must first be screened without model
outputs. If they lack a behaviorally distinct, lifecycle-identifiable
intervention, new non-source scenario families must be acquired before any
held-out model validation.
