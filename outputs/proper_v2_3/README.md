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

## Pending Qwen five-condition development

The frozen Qwen runner will write one unique result directory under
`qwen_five_condition_development_remote/`. No v2.3 model result exists at the
time of this protocol freeze. Smoke failures and completed negative stage
gates must be retained; this development run cannot create a held-out or
confirmatory claim.
