# PROPER v2.3 outputs

Generated v2.3 artifacts belong in versioned subdirectories here. They are
ignored by default and may be force-added only by exact, audited result
directory after a stage completes.

Never copy or regenerate frozen v2.x results into this namespace.

The first local stage writes only CPU/scripted validation to
`first_stage_validation/results.json`. That artifact is not model evidence and
does not authorize a GPU run.

## Frozen remote tau3 CPU branch-screen runs

Both remote run directories below are preserved without editing or
replacement:

- `20260801T091416Z-amax-44e5b11104e3`: protocol v1 infrastructure-negative
  envelope. The 12-pair branch screen and its schema passed, but the envelope
  failed because the broad 245-test repository gate selected legacy tests with
  fixtures absent from the clean handoff. It recorded 1 failure and 8 errors.
  This is not a method, model-completion, or safety-negative result.
- `20260801T094645Z-amax-43381b2a1295`: corrected protocol v2 remote CPU
  development validation. It passed all 64 scoped v2.3 tests with zero
  failures and errors. Its 12-pair result contains four read-only, four
  idempotent-state-setting, and four non-idempotent-side-effect pairs.

The raw `branch_screen.json` SHA-256 for both runs is
`24b9967ac3790d5056f716899791469ee017400fc7a34a32d8adecb14a579eae`.
The protocol-v1 and protocol-v2 `remote_validation.json` SHA-256 values are,
respectively,
`24eb3ec09b233e027f533bd03e8158547a5f825bb94880eaf123c7fae743d330`
and
`db50cebbf650a90ea9461c4193b4a3ca9070eeb1379c4b2c5be0a4425d667209`.

The passing run establishes remote scripted lifecycle, continuation, repeat
safety, and branch capacity only. It supplies no selector, model completion,
held-out, GPU, or confirmatory evidence. New held-out capacity remains zero;
the next gate is to freeze the five-condition development protocol before any
model execution.

## Frozen five-condition preparation runs

The first remote preparation at revision `956bee5` generated
`five_condition_development/prepared_manifest.json` and then stopped before
tests because schema v1 rejected the three legitimate pre-action records whose
`branch_prefix_recipe` is null. Its SHA-256 is
`11b062d601d8c3c9582fd006020c4fbb141b973f22f0bf06fbe61d0af5de4ee9`.
This is a preserved infrastructure-negative preparation artifact, not method
or model evidence.

Validation protocol v2 passed in remote run
`20260801T104150Z-amax-b701bafa4630` at remote project revision
`b701bafa4630cc59555ab3ecf77c6bd7f21b04bd`:

- prepared manifest SHA-256:
  `f7f29d03753423351f49f4790ecd18d3c767a1bb3f0f073dccbfa7532768c85a`;
- preparation validation SHA-256:
  `e2822620a16336c452d3d6ab8ffc239cbb4638243f30a56aaaa2a22849f6933e`;
- 12 pairs, 60 conditions, with 3 pre-action and 9 post-failure pairs;
- 11/11 frozen input hashes and all preparation checks passed;
- 72/72 scoped tests passed with zero failures, errors, or skips;
- model runner implemented: false; model/GPU/target execution: false;
- held-out capacity and model/confirmatory authorization: zero/false.

This passing result authorizes only the next code stage: implement, validate,
and freeze a separate guarded development model runner before considering GPU
authorization. It is not selector, completion, safety, cost, or confirmatory
model evidence.

## Frozen guarded-runner CPU validation

Remote run `20260801T112852Z-amax-7aa3f0256e0d` passed at remote revision
`7aa3f0256e0d022f10fc79cec7f6998a917d15a6`:

- validation-envelope SHA-256:
  `88a4a0750c05c6ab46272c9383ad609228d0c1c5b17f28445e44982fd30d7f22`;
- scripted 12x5 result SHA-256:
  `56b134e49694803c5bf95e1cf0c91819353dcc78b6fd777d3022211e9b718480`;
- 9/9 integration and safety checks passed;
- 80/80 scoped tests passed;
- 13 duplicate proposals were blocked;
- every allowed execution was resolved in the complete ledger;
- no duplicate non-idempotent execution occurred;
- model loaded/GPU used/model-output read: false/false/false.

This is scripted runner evidence, not model completion or confirmatory
evidence. It authorizes freezing a separate Qwen development runner but does
not itself constitute a Qwen run.

## Frozen Qwen five-condition development

Remote run `20260801T122152Z-amax-0044e8fd6417` completed all 12 pairs and 60
conditions at revision `0044e8fd64177ddcbe3301bd44b639dea0e8140c`.
Its `results.json` SHA-256 is
`3853d82e4ac048e2821cbb06185ffe6b2ee8e58f52445f234176fc2733bcbe60`.

The smoke and integrity gates passed, and duplicate non-idempotent execution
was zero. The stage gate stopped because v2.3 post-failure completion remained
0/9, not strictly better than condition four's 0/9. The full-ledger controller
removed identical post-branch repeats (0 versus 8) but reduced mean partial
similarity (0.5233 versus 0.6815) and increased post-failure total tokens by
49.3%. The complete endpoint-separated report is in
`docs/proper_v2_3/qwen_five_condition_development_result.md`.

This negative development result is frozen. It is neither held-out nor
confirmatory and must not be tuned on these same 12 pairs.

## PlanBench-XL source qualification

`planbench_xl_source_qualification/source_qualification.json` records the
read-only qualification of upstream revision
`a0dacc2d227e197a61011a68d3b15c24aebbb2a1`. It contains no model output.
Its SHA-256 is
`90ef60e2670cde2c1d9628f19fde14b9eca5e249338234eef3fbb181bec1d121`.
The structural continuation pool is 322, but accepted full-PROPER-v2.3
capacity is zero because all 185 baseline tools are read-only. No model or GPU
run is authorized.

## Tau3 execution-state continuation screen

`tau3_execution_state_continuation_screen/screen.json` replays the frozen 12
balanced tau3 development ledgers through the observable progress layer. All
12 scripted handoffs passed. The file SHA-256 is
`d954248cc05814f32759b02839584378b6cfe16bbec60bcfe98356c0ee35038c`.
This authorizes protocol design only, not a model or GPU run.

## Tau3 model-protocol feasibility gate

`tau3_model_protocol_feasibility/audit.json` records the CPU-only check that
precedes any tau3 model-protocol freeze. All 12 source action mappings pass,
but only four public `pre_action` starts are model-ready and zero of eight
`post_failure` starts have the required frozen public branch artifacts.
`validation.json` freezes the stage hashes and scoped-test result. The gate
therefore stops before model-protocol freezing or runner implementation; no
task, model, model output, or GPU was used.

## Public branch capture design

`public_branch_capture_design/scripted_traces.json` contains three CPU-only
traces for public/evaluator state separation and identical-start hashing.
`validation.json` freezes the stage inputs and validation result. Successful or
outcome-unknown non-idempotent effects are represented in the evaluator-side
checkpoint and receive an empty environment replay history, preventing branch
initialization from repeating the effect. This authorizes only a CPU tau3
runtime adapter, not a model runner or model/GPU execution.

## Tau3 branch replay adapter

`tau3_branch_replay_adapter/validation.json` freezes the local CPU adapter
stage. It validates the split participant/environment initialization boundary
using fake environments and authorizes only the one-shot native tau3 CPU smoke.
The native smoke result belongs under
`tau3_branch_replay_native_smoke/result.json` after remote execution; until it
is returned and frozen, real branch capture and all model/GPU work remain
unauthorized.

The first remote attempt stopped at the protocol-v1 Python 3.12 guard before
tau3 import or native execution. Protocol v2 accepts Python 3.11/3.12 under the
existing source-checkout contract. This is an infrastructure-only correction;
the failed attempt contains no method or model evidence.

Protocol v2 subsequently stopped on an unused top-level batch-runner `pandas`
import before constructing the retail environment. Protocol v3 loads only the
required pinned tau2 source modules through a lightweight namespace. No native
action ran in v2, and the adapter and scientific gates are unchanged.

The protocol-v3 native result passed and is frozen in
`tau3_branch_replay_native_smoke/result.json` with SHA-256
`ef8fac9162e28af8ea0b9f552b370ffffb9d9289482eef40be604d9885166a14`.
`local_freeze_validation.json` independently checks its schema, revisions,
configuration hash, nine gates, single native execution, checkpoint round trip,
and closed model/GPU claims. It authorizes public branch capture protocol design
only.

## Real public branch capture protocol

`real_public_branch_capture_protocol/validation.json` is the CPU-only protocol
design validation. It checks the frozen 12-pair development partition, public
action/verifier registry, separate failed versus unknown injection semantics,
evaluator/method field separation, one-attempt stop policy, input hashes, and
closed future-manifest schema. It authorizes acquisition-runtime freezing only;
no task, model, or GPU was used.
