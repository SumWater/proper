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
