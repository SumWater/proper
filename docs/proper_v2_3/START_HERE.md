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

## Current gate after execution-state continuation design

The CPU-only execution-state continuation design was frozen at project commit
`8610118`. It adds observable subgoal handoff and bounded progress routing
without rerunning the existing 12 pairs. Its four scripted traces passed; this
is implementation evidence only, not a model-completion result.

PlanBench-XL source revision
`a0dacc2d227e197a61011a68d3b15c24aebbb2a1` was then qualified read-only.
Its 322 nonempty explicit-blocker plans form a structural continuation pool,
but all 185 baseline tools are read-only: there are zero idempotent state
settings and zero non-idempotent side effects. The repository also contained
no root license file, and no prospective Qwen3-8B base-capability gate was
run. Therefore accepted full-v2.3 candidate capacity remains zero and no model
or GPU run is authorized. See `planbench_xl_source_qualification_result.md`.

The previously frozen 12-pair tau3 scripted branch result was then replayed
through the execution-state continuation layer. All four read-only, four
idempotent-state-setting, and four non-idempotent-side-effect pairs completed
both scripted subgoal handoffs; every ledger was resolved and every
non-idempotent native action remained single-execution. The replay result
SHA-256 is
`d954248cc05814f32759b02839584378b6cfe16bbec60bcfe98356c0ee35038c`.
This authorizes freezing a tau3 development protocol only. It remains
development-only, adds no held-out capacity, and authorizes no model or GPU
run. See `tau3_execution_state_continuation_screen_result.md`.

## Current gate after tau3 model-protocol feasibility audit

The CPU-only audit in `tau3_model_protocol_feasibility_result.md` confirms that
all 12 candidate action references still map to the pinned tau3 source. Only
the four read-only `pre_action` candidates can start from public task-opening
information. None of the eight `post_failure` candidates has a frozen public
conversation prefix, matching environment initialization, public failure
receipt, and identical-start replay proof.

Consequently the current counts are 4/12 model-ready overall and 0/8
model-ready for `post_failure`. Model-protocol freezing, model-runner
implementation, model execution, and GPU use are not authorized. The next
permitted work is a CPU-only design for public branch capture that does not
expose task IDs, future gold actions, recoverability labels, or evaluator
outcomes to the method.

## Current gate after public branch capture design

`public_branch_capture_design.md` now freezes the scenario-neutral separation
between complete participant-visible history and evaluator-only environment
checkpoints. Three scripted CPU traces cover a read-only pre-action trigger, an
idempotent setting failure without execution, and a non-idempotent action whose
native execution succeeded but public result is unknown. Five planned
development conditions receive an identical start hash in every trace, and
checkpointed effects are never replayed into the environment.

This design authorizes only a CPU-only tau3 runtime adapter that initializes
participant histories and environment state through separate channels. It does
not authorize constructing prefixes from gold actions, running the existing 12
tasks through a model, implementing a model runner, or using a GPU. The eight
real post-failure branches remain missing until that adapter captures and
replays public evidence without evaluator leakage.

## Current gate after local tau3 replay-adapter validation

The split-state environment adapter and its remote native CPU smoke entry are
frozen in `tau3_branch_replay_adapter.md`. Local fake-environment tests verify
checkpoint restoration, complete public-history integrity, zero mutation
replay, restored-state hashing, rejection of task initialization merging, and
single initialization. The local machine cannot perform the native smoke
because its bundled Python lacks tau3's `loguru` dependency.

The next permitted action is the one-shot remote CPU command in
`tau3_branch_replay_native_smoke_handoff.md`. It dynamically selects one
pending order from a fresh in-memory retail database, executes cancellation
once, restores the post-action checkpoint in a second fresh environment, and
verifies that no mutation was replayed. It loads no benchmark task or model.
No real branch capture, model protocol, model runner, or GPU use is authorized
before that native smoke passes and its result is returned and frozen locally.

The first remote smoke attempt stopped before tau3 import because protocol v1
required Python 3.12 while the active remote environment was Python 3.11.15.
No native action, task, or model ran. Protocol v2 now permits Python 3.11 or
3.12, matching the earlier frozen tau3 source-checkout execution contract; no
adapter behavior, fixture action, evaluator, or pass gate changed. Rerun the
same one-shot command after synchronizing the protocol-v2 files.

That protocol-v2 retry stopped before retail-environment construction because
tau2's top-level package eagerly imports the unused batch runner and its
`pandas` dependency. Protocol v3 uses a lightweight namespace for the pinned
source and imports only the retail environment modules required by the smoke.
No native action, task, or model ran, and no method or pass gate changed.

## Current gate after native tau3 replay smoke

The protocol-v3 remote native CPU smoke passed at remote revision
`bcc758badf692932008824d0d0d05fcda865a177`. One isolated
`cancel_pending_order` action executed, and a second fresh environment restored
the post-action checkpoint with empty mutation replay. All nine checks passed;
the checkpoint hashes matched exactly. No task, model, model output, or GPU was
used. See `tau3_branch_replay_native_smoke_result.md`.

This result authorizes only freezing the real public branch capture protocol.
It does not yet authorize capturing the eight missing post-failure branches,
running the 12 development tasks, freezing a model protocol, implementing a
model runner, or using a GPU.

## Current gate after real public branch capture protocol design

`real_public_branch_capture_protocol.md` now freezes the acquisition semantics
before any development task is run. Each pair gets one ordinary public
`no_memory_baseline` acquisition attempt with no gold-scripted prefix,
resampling, or replacement. Pre-action branches stop after the initial public
user message; idempotent settings receive a visible non-executed reference
failure; non-idempotent actions execute exactly once and receive a public
unknown-result receipt backed by the post-action checkpoint.

The action/verifier registry is based on public tool contracts and covers all
nine guarded tool names with read-only verification where declared. Pair/task
routing remains evaluator-only. The validated design authorizes freezing the
complete acquisition runtime only. It does not authorize running the 12 tasks,
capturing branches, freezing a comparison model protocol, implementing a model
runner, or using a GPU.

## Current gate after acquisition-runtime feasibility audit

`acquisition_runtime_feasibility_result.md` records a CPU-only stop before
runtime freezing. The prior local Qwen3-8B worker is agent-tested but text-only:
it has no tau3 tool-message/tool-call interface. Tau3's default user simulator
uses external GPT-4.1 through LiteLLM, while this project has no frozen external
endpoint, credentials boundary, network authorization, or user-model revision.
Qwen3-8B has not been validated as the tau3 user simulator, and the model
directory lacks a frozen content manifest.

The next permitted work is limited to implementing CPU-contract-tested local
Qwen agent/user participant adapters and producing a remote read-only model
inventory. Acquisition-runtime freezing, task execution, branch capture,
external API calls, model loading, model runner work, and GPU use remain
unauthorized.

## Current gate after local tau participant adapter validation

`local_tau_participant_adapter.md` freezes the CPU-only boundary between tau
public messages and the existing text-only Qwen JSONL worker. Separate agent
and user prompts, canonical public tool records, deterministic requests,
exclusive JSON decisions, public tool-schema validation, and symmetric
evaluator-metadata rejection are covered by eight scoped tests. The validation
hashes all four contract inputs and uses no task, model output, model load, or
GPU.

Passing this stage authorizes only a remote read-only content inventory of the
known Qwen model directory. It does not authorize an acquisition runtime,
running the 12 development tasks, capturing branches, implementing a model
runner, calling an external endpoint, or using a GPU.

## Current gate after Qwen inventory preparation

`qwen_model_inventory_preparation.md` freezes the exact remote model path,
streaming per-file SHA-256 contract, canonical manifest, unique result path,
revision/worktree guards, and stop-closed handling of empty directories,
symlinks, and special entries. The local preparation uses only temporary toy
files and imports no model or tau library.

The next permitted action is the one-shot remote CPU command in
`qwen_model_inventory_handoff.md`. Its result must be returned and frozen
locally. Model loading, task execution, acquisition, branch capture, model
runner implementation, external APIs, and GPU use remain unauthorized.

## Current gate after Qwen inventory result freeze

`qwen_model_inventory_result.md` freezes both clean-worktree preflight failures
and the passing remote inventory. The passing revision contains 15 regular
files totaling 16,397,461,266 bytes with canonical manifest SHA-256
`f981a4a7978fd128d6efb18d93b8810d98434a8e69c9bd517ad7aa4e5c1b6a07`.
Local validation independently recomputes the manifest, paths, counts, totals,
and result hashes without accessing model files.

The next permitted work is acquisition-runtime protocol design only. The
inventory establishes exact content identity, not model compatibility or
performance. Model loading, task execution, real capture, a comparison runner,
external APIs, GPU use, and confirmatory claims remain unauthorized.

## Current gate after acquisition runtime protocol design

`acquisition_runtime_protocol.md` freezes the complete half-duplex turn loop,
all 30 airline/retail public action-effect contracts, full-ledger duplicate
safety, 12 task-component hashes, Qwen manifest and generation settings,
independent acquisition budgets, cost endpoints, persistence, exclusions, and
stage stops. Twelve state-machine tests and eight scripted checks pass without
a model, task, model output, or GPU.

The next permitted work is implementation of this exact runtime plus a
synthetic CPU dry-run. Model loading, the 12 development attempts, real public
branch capture, a comparison runner, external APIs, GPU use, and confirmatory
claims remain unauthorized.

## Current gate after acquisition runtime implementation

`acquisition_runtime_implementation.md` records the completed executable
runtime and synthetic CPU validation. Eleven scoped tests pass without
resource warnings and all 15 synthetic checks pass. The dry run covers all
three action-effect classes plus invalid JSON, worker failure, ambiguous
non-target state change, and duplicate successful state-change stops. It uses
no tau3 task, model, model output, external endpoint, or GPU.

Two pre-model implementation corrections are explicit and versioned: actual
initialized checkpoint evidence replaces the pre-action placeholder, and an
ambiguous non-target write now saves its post-action checkpoint and stops. The
frozen protocol-v1 simulator and its evidence were not overwritten.

The next permitted work is design and freeze of a separate one-shot real
acquisition-runner protocol. Model loading, real acquisition of the 12
development branches, comparison-runner implementation, external APIs, GPU
use, and confirmatory claims remain unauthorized.

## Current gate after one-shot acquisition-runner protocol design

`acquisition_one_shot_runner_protocol.md` freezes the future remote preflight,
separate tau/Qwen Python environments, persistent JSONL worker, pair order,
pre-action smoke, no-retry/no-resume failure policy, atomic persistence, cost
endpoints, and pass gate. Thirteen validation checks and six scoped tests pass
without importing tau3 or model libraries.

The versioned run envelope also closes a pre-model representational conflict:
the old manifest required exactly 12 attempts even when the protocol stopped
after the first failure. The old schema remains frozen; the new envelope
preserves zero-attempt preflight failures and 1–12 actual acquisition attempts.

The next permitted work is local implementation and CPU-only validation of the
one-shot runner. The frozen command template is not yet authorized. Model
loading, task execution, real capture, remote execution, GPU use, and
confirmatory claims remain closed.
