# PROPER v2.3 development handoff

## Status

PROPER v2.3 is a new development line created after the frozen v2.2.1 model
outputs were inspected. It explores execution-aware memory lifecycle for
broader Agent-memory applicability. It is not part of the two confirmatory
PROPER v1 results, and no v2.3 confirmatory or GPU run is currently authorized.

The validated paper core remains PROPER v1: conservative, observable-evidence
failure-memory selection improved Qwen3-8B Recovery Validity in frozen
argument-omission and released transient-authorization experiments. PROPER
v2.x investigates whether that principle can be unified and extended to
different decision phases and stateful multi-step tool use.

## Frozen ancestry

Do not modify, move, overwrite, or regenerate files committed at these points:

- unified v2 and v2.1 development evidence: `1d4a95d`;
- v2.2 lifecycle development evidence: `35ec8b2`;
- v2.2.1 continuation development evidence: `d6b7c8c`.

Key immutable result identities:

- v2.1 Qwen result:
  `3ec804cb5d8e0ba98e60d36099a525210965b6fcfe1ddf9426549b938bc3f07a`;
- v2.2 Qwen lifecycle result:
  `de84767fc3136e1832210d5c1692a12302f3b1551e1efbb4a7cafcc889dd83a1`;
- v2.2.1 four-condition prepared manifest:
  `3efcd90ee2e8b30685430326c1d1781caec15c35c6fd8ee28dfd066e13c89f21`;
- v2.2.1 static validation:
  `e43191d93c148f4fccd5cbdea7726f7e82f51fcc55b6626eb400a2806c52caf1`;
- v2.2.1 frozen Qwen config:
  `e898f2d8fa0837ac817e3bece6aeb62ca7fdf5f9c50b83971629607085da6686`;
- v2.2.1 Qwen result:
  `541f764abb25f6719f633b8189d87e3b6177825db42087725efc5d32518fc6e8`;
- v2.2.1 prospective inventory:
  `a969e50b35671bbba3641c7a33640c7e7ca5a452a608536612546c94808a48b9`.

The 12 ToolSandbox pairs used by v2.1, v2.2, and v2.2.1 are permanently
development-only. They may be referenced read-only for regression and method
development, but cannot become held-out or confirmatory targets.

## Observed development boundary

The evidence must remain endpoint-separated:

- selector: PROPER improves first-decision policy alignment;
- lifecycle: all 9 post-failure memories were consumed and handed back to
  ordinary planning;
- recovery continuation: v2.2.1 blocked 10 exact consumed-recovery-action
  repeat proposals and accepted replans;
- final completion: all 9 post-failure tasks remained incomplete;
- safety: 8 later ordinary-task repeats were executed, including 4 duplicate
  message sends;
- cost: controller replans increased post-failure total tokens by 36.5%
  relative to lifecycle prompt-only;
- target capacity: the no-play inventory found 0 eligible candidates among
  1,032 ToolSandbox scenario names.

The narrow v2.2.1 success is recovery-action deduplication. It is not evidence
of general continuation safety or task completion.

## v2.3 research question

Can one scenario-independent, observable-evidence-only controller combine
memory selection, memory lifecycle, and execution control so that a
stateful tool Agent:

1. applies an applicable memory at the correct decision phase;
2. verifies success evidence before consuming it;
3. returns to ordinary task planning;
4. prevents unsafe repetition of any successful or side-effecting action, not
   only the selected recovery action;
5. retains bounded retry, verification, replan, and stop behavior;
6. improves final task completion without hiding safety or cost regressions?

This question is broader than the frozen v2.2.1 continuation contract and must
use a new method version.

## Required method boundary

The v2.3 interface must remain common to `pre_action` and `post_failure`:

```text
ObservableRecoveryState
+ selected MemoryPolicyCard
+ MemoryLifecycleState
+ ActionExecutionLedger
-> allow | verify | replan | stop
```

Scenario name, semantic-family name, benchmark recoverability, gold action,
evaluator outcome, and prior model result are forbidden method inputs.
Scenario differences must be represented by public state, tool schema,
declared action effects, success evidence, and retry-safety evidence.

The action ledger must cover the complete trajectory. At minimum, it needs:

- normalized tool and argument identity;
- proposed, executed, succeeded, failed, and outcome-unknown states;
- success-evidence provenance;
- read-only, idempotent state-setting, and non-idempotent side-effect classes;
- repeat and verification policy;
- separate retry, verification, invalid-decision, and replan budgets;
- a fail-closed stop reason.

Do not add scenario-specific provider branches to make the 12 development
pairs pass.

## Development design

The existing 12 pairs may support a same-start development comparison:

1. TF-IDF persistent memory;
2. unified PROPER persistent memory;
3. PROPER lifecycle prompt-only;
4. frozen v2.2.1 recovery-action controller;
5. v2.3 full action-ledger controller.

Report separately:

- selector first-decision alignment;
- memory state transitions and success evidence;
- consumed recovery-action proposals and executions;
- all repeated actions, split by effect class;
- duplicate non-idempotent side effects;
- final task completion and partial progress;
- tool exceptions and minefields;
- model requests, tool calls, tokens, and controller-induced overhead.

Development results cannot authorize a confirmatory claim.

## Gates before any model run

Complete one local stage before asking for remote execution:

1. contract, schema, state machine, policy configuration, and interpretation
   boundary;
2. dependency-light unit tests for every state transition and budget;
3. regression tests proving frozen v1/v2 hashes remain unchanged;
4. scripted multi-step tests with no scenario-specific branches;
5. preparation and runner-validation entry points;
6. one folder-level synchronization list and one guarded remote command.

No GPU run is justified until all local gates pass.

## Gates before any confirmatory run

A future confirmatory stage additionally requires:

- genuinely unexposed targets outside the exhausted current ToolSandbox pool;
- multiple failure-policy and action-effect families;
- a frozen CPU selector/capacity screen;
- recoverable-branch verification without playing targets through a model;
- method, memory bank, prompts, model settings, endpoints, exclusions, and
  stopping rules frozen before model outputs;
- sufficient behaviorally changed pairs for a prespecified paired analysis.

If new target capacity is unavailable, or development still produces duplicate
non-idempotent side effects or zero post-failure completion improvement, stop
v2.3 rather than tune a frozen protocol after results.

## Workspace layout

- method and protocol: `docs/proper_v2_3/`;
- configuration: `configs/proper_v2_3/`;
- experiment entry points: `experiments/proper_v2_3/`;
- schemas: `schemas/proper_v2_3/`;
- generated structured artifacts: `outputs/proper_v2_3/`;
- Python implementation: `src/failure_memory/proper_v2/v2_3/`;
- tests: `tests/test_proper_v2_3_*.py` and
  `tests/test_toolsandbox_v2_3_*.py`.

New work may read frozen artifacts by explicit path and SHA-256. It must never
write into `outputs/proper_v2/`.

## First task in the next development session

Do not implement a model runner first. Begin with:

1. an action-effect and idempotency contract based only on public tool
   information;
2. an execution-ledger state machine with explicit unknown-outcome handling;
3. a capacity audit for genuinely unexposed multi-step targets;
4. unit tests and scripted traces that include duplicate messaging and
   state-setting regressions.

Only after those artifacts are reviewed should the five-condition development
runner be prepared and frozen.

## Current gate after the remote tau3 CPU screen

The protocol-v2 remote tau3 screen passed at run
`20260801T094645Z-amax-43381b2a1295`; its frozen envelope remains development
scripted evidence only. The next versioned stage is
`five_condition_development_protocol.md` and its CPU-only preparation contract.

That preparation uses the original 12 model-exposed ToolSandbox pairs for a
same-start development regression and adds
`proper_v2_3_full_ledger_controller` as the fifth condition. Tau3 pairs are not
mixed into that comparison. Preparation validation still authorizes no model
runner or GPU use; a separate guarded runner must be implemented, reviewed,
and frozen in a later commit before any model execution.

The protocol-v2 five-condition preparation subsequently passed at run
`20260801T104150Z-amax-b701bafa4630`; the passed prepared-manifest SHA-256 is
`f7f29d03753423351f49f4790ecd18d3c767a1bb3f0f073dccbfa7532768c85a`.
The current gate is the CPU-only scripted guarded-runner validation described
in `guarded_runner_validation_handoff.md`. It deliberately probes duplicate
successful actions across the full ledger and the non-idempotent-action guard,
while loading no model and using no GPU. Only a preserved passing remote
envelope may advance to freezing the real Qwen development runner.

That gate passed in remote run
`20260801T112852Z-amax-7aa3f0256e0d`: all 9 integration checks and 80 scoped
tests passed, with 13 duplicate proposals blocked and zero duplicate
non-idempotent executions. The current task is now to freeze the separate Qwen
development runner, its exact input hashes, reporting endpoints, stop rules,
and one-shot remote command before any v2.3 model output is generated.

The Qwen runner is now defined by
`toolsandbox_qwen_five_condition_development_v2_3.json` and
`qwen_five_condition_development_handoff.md`. Its 14 direct inputs, five
condition order, deterministic model settings, six endpoint groups, exclusions,
independent budgets, smoke gate, and safety/completion/integrity stops are
fixed before model output. The next permitted action is its one-shot remote
development command; changing this protocol after that output is not allowed.

That one-shot run subsequently completed at
`20260801T122152Z-amax-0044e8fd6417`. Safety improved—identical post-branch
repeats fell from 8 to 0 and duplicate non-idempotent execution remained
zero—but post-failure completion remained 0/9, partial similarity fell versus
condition four, and post-failure total-token cost rose 49.3%. The prespecified
completion gate therefore stopped this development line on the existing 12
pairs. See `qwen_five_condition_development_result.md`; do not retune and rerun
this frozen cohort.
