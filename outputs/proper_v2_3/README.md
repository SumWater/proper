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

## Acquisition runtime feasibility

`acquisition_runtime_feasibility/audit.json` freezes the CPU-only negative
runtime audit. It confirms the prior Qwen agent evidence while recording the
missing tau tool interface, local user-simulator adapter, prompts/contracts,
model manifest, and remote inventory. The audit authorizes adapter and
read-only inventory implementation only; acquisition and all model/GPU work
remain closed.

## Local tau participant adapter

`local_tau_participant_adapter/validation.json` is a CPU-only contract result
covering separate agent/user context, canonical public tool messages, strict
JSON decisions, public tool-schema validation, evaluator-metadata rejection,
deterministic worker requests, and closed task/model/GPU gates. It contains no
model output and authorizes only a remote read-only Qwen model-directory
inventory. It is not runtime, capture, completion, safety, or confirmatory
evidence.

## Qwen model inventory preparation

`qwen_model_inventory_preparation/validation.json` freezes the dependency-free
remote inventory entry, exact model path, closed schema, input hashes, and toy
filesystem tests. It contains no remote model bytes or model output and
authorizes only one read-only remote inventory. The returned inventory belongs
under a unique `qwen_model_inventory_remote/` run directory and must be frozen
locally before any later runtime decision.

## Frozen Qwen model inventories

All three returned run directories are preserved. Runs `20260802T042437Z` and
`20260802T042501Z` stopped at the dirty-worktree preflight with zero files and
bytes. Run `20260802T042655Z` passed at remote revision `a740a864f8fe...`,
recording 15 files, 16,397,461,266 bytes, and manifest SHA-256
`f981a4a7978fd128d6efb18d93b8810d98434a8e69c9bd517ad7aa4e5c1b6a07`.
`qwen_model_inventory_freeze/validation.json` checks all three exact result
hashes and recomputes the successful manifest. These artifacts identify model
directory contents only; no model was loaded and no task or GPU ran.

## Acquisition runtime protocol

`acquisition_runtime_protocol/validation.json` freezes the CPU-only protocol
validation; `scripted_traces.json` contains six public-state traces and eight
checks. The validation covers 30/30 public tools, 12/12 task-component hashes,
complete-ledger duplicate safety, participant separation, zero invalid-output
retry, independent budgets, and closed model/task/capture/GPU gates. It
authorizes runtime implementation and synthetic CPU dry-run only, not model
loading or real branch acquisition.

## Acquisition runtime implementation

`acquisition_runtime_implementation/synthetic_dry_run.json` contains seven
synthetic attempts: three successful effect-class captures and four deliberate
transport or safety failures. Its SHA-256 is
`add4254f16d193f342ac3b5255b90537ee49a265a42f914c4d4bd278009d3caf`.
`validation.json` records 11 passing scoped tests and 15 passing synthetic
checks, with model, task, tau3, external endpoint, capture, and GPU boundaries
closed. Its SHA-256 is
`09b1e92e85a2103f25f7024a7ce7cd97717bec366a46ab3b3a4fff0e16634b72`.

This is synthetic implementation evidence, not model completion or safety
evidence. It authorizes one-shot real-runner protocol design only; it does not
authorize model loading or real branch acquisition.

## One-shot acquisition-runner protocol

`acquisition_one_shot_runner_protocol/validation.json` records 13 passing
design checks and six passing scoped tests. Its SHA-256 is
`52443099f6e6270e124e412bb841e45f3ed726f166f0076e8f2e6be1354353b4`.
The result loads no model, reads no model output, executes no task, and uses no
GPU. It authorizes local runner implementation and CPU validation only; the
frozen remote command remains unauthorized.

## One-shot acquisition-runner implementation

`acquisition_one_shot_runner_implementation/validation.json` records 16
passing implementation checks and 24 passing scoped tests. Its SHA-256 is
`025dc3aa1637cf8db0973b780732e2e1dac97155c5d90b1ea9909a870a343579`.
The validation itself loads no model, reads no model output, executes no task,
and uses no GPU. It authorizes the single command in
`docs/proper_v2_3/tau3_acquisition_remote_handoff.md`; any returned success,
failure, or interruption must be frozen before further work.

## Frozen tau3 acquisition preflight failure

Remote run `20260803T064447Z-amax-8c2b38219291` is preserved under
`tau3_acquisition_remote/`. Only the clean tracked-worktree check failed; all
other 11 preflight checks passed. It contains no model/task/GPU execution. The
preflight and result SHA-256 values are respectively
`c2e4afae302bae7fecf035d1135de83bf344b5eb32c5b11291a0b74322ab078a`
and `221131fd27a99c3119e13f80b95b79adae2b81990b39448da95f99733bd54194`.

`tau3_acquisition_preflight_failure_freeze/validation.json` passes 13 checks;
its SHA-256 is
`f8616896b2efd4646718f09276f76333efc6261823035c3cda7469ef04d74fef`.
It authorizes one identical-command retry only after the four reported README
changes are committed and tracked status is empty.

## Frozen stopped tau3 acquisition

Remote run `20260803T071028Z-amax-8fd7c469ec70` passed all preflight checks,
loaded the local Qwen model, used GPU 0, and executed tau3. It captured four
pre-action branches and stopped on the fifth pair with
`invalid_user_output`; no retry or sixth attempt occurred. Zero post-failure
branches were captured. The fifth attempt contains one failed read-only lookup
and no target or non-idempotent side-effect execution.

The returned aggregate reports 7 requests, 11,366 prompt tokens, and 444
completion tokens. Raw worker-record audit reports 8, 12,040, and 483 because
the invalid response's 1 request, 674 prompt tokens, and 39 completion tokens
were omitted. Original artifacts remain unchanged.

`tau3_acquisition_result_freeze/validation.json` validates preservation and
audit integrity. It does not make the scientific stage pass: rerun, resume,
comparison protocol, and confirmatory claims remain closed.

## AppWorld source-qualification design

`appworld_source_qualification_design/validation.json` records 14 passing
CPU-only design checks. It uses primary-source metadata only and performs no
download, source inventory, decryption, task reading, ground-truth access,
model loading, model output reading, or GPU use. Candidate count is null.

The result permits design of an offline encrypted-source acquisition and
static-inventory protocol only. It does not authorize acquisition, task play,
target selection, model execution, or held-out/confirmatory claims.

## AppWorld offline-wheel inventory preparation

`appworld_offline_wheel_inventory_preparation/validation.json` records 12
passing preparation checks and five passing synthetic reader tests. No official
wheel was downloaded or read, and no package, task, model, or GPU was used.

It authorizes one read-only inventory of the exact external wheel only. A
returned result must be frozen before any installation or source decision;
installation and all later scientific gates remain closed.

## Frozen AppWorld wheel inventory

Remote run `20260803T081514Z-amax-cc297f055b04` records 44 wheel members,
1,272,412 total uncompressed bytes, and two encrypted `.bundle` members. All
preflight checks passed. No extraction, decryption, import, task/API read,
model load, or GPU use occurred.

`appworld_wheel_inventory_result_freeze/validation.json` independently checks
the returned result hash, canonical member manifest, safe paths, counts, sizes,
and both encrypted bundle records. It authorizes controlled-install protocol
design only, not installation or scientific execution.

## AppWorld controlled-install protocol design

`appworld_controlled_install_protocol/validation.json` records 14 passing
checks and six scripted stop-closed traces. It decrypts and extracts nothing,
reads no API/task/evaluator content, and uses no model or GPU.

The result authorizes implementation and synthetic validation of an
aggregate-only apps-bundle inspector. Protected decryption, official install,
data download, static API inventory, and all scientific gates remain closed.

## AppWorld apps-bundle inventory implementation

`appworld_apps_bundle_inventory_implementation/validation.json` records 12
passing implementation checks and seven passing synthetic encrypted-archive
tests. Only synthetic bundles were decrypted; no real protected material,
source, task, model, or GPU was accessed.

It authorizes one remote aggregate-only inventory of the exact apps bundle.
All installation, extraction, tests/data/API access, and scientific gates stay
closed until the returned result is frozen.

## AppWorld apps-bundle inventory preflight failure

Remote run `20260806T015829Z-amax-dd1cd0026747` stopped before decryption
because the selected Python environment did not provide `cryptography`.
Revision, frozen hashes, clean-tree, external-wheel, and safety-boundary checks
passed. No protected plaintext, source, task/API content, model, or GPU was
accessed.

The result is preserved as infrastructure evidence, not a method or candidate
inventory result. Inventory retry remains closed. The next gate is design of
offline or hash-pinned dependency provisioning without changing scientific
inputs.

`appworld_offline_dependency_repair/validation.json` authorizes one offline
repair invocation using three exact wheels in a new external target. It does
not itself install dependencies or decrypt the apps bundle.

## Frozen AppWorld aggregate apps-bundle inventory

Remote revision `8260a8c00e97...` passed offline provisioning and inventory.
The archive contains 96 files and 1,017,074 uncompressed bytes. Only aggregate
extension counts and path/content hashes were retained; protected plaintext
was not persisted and source was not extracted.

This is structural capacity evidence, not API-effect coverage, candidate
qualification, held-out evidence, or a PROPER result. Inventory rerun is
closed. In-memory static API-inventory protocol design is the next gate.

`appworld_static_api_protocol/validation.json` records the local design gate.
It uses only scripted traces and authorizes implementation with synthetic
archives; it does not authorize real bundle decryption or target selection.

`appworld_static_api_inventory_implementation/validation.json` records the
hash-only AST implementation gate. Ten synthetic source tests pass. No real
bundle was decrypted, and real inventory remains closed pending a separately
frozen guarded runner.

`appworld_static_api_inventory_runner/validation.json` records the frozen
guarded runner gate. Only synthetic bundles were decrypted during validation.
It authorizes one real hash-only static inventory and no rerun.

## Frozen AppWorld static API inventory

The one-shot inventory safely produced 1,035 hash-only callable records: 376
read-only, zero proven idempotent setters, zero proven non-idempotent effects,
and 659 unknown. Full effect coverage therefore failed.

This is a negative source-qualification result under the frozen conservative
static proof rules, not a PROPER result and not evidence that AppWorld lacks
state-changing APIs. Rerun, post-result rule tuning, target selection, task
access, and model execution are closed; the AppWorld route stops here.
