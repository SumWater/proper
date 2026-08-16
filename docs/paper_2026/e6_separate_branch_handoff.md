# E6 separate-branch handoff

## Current-paper boundary

The current paper freezes P0--E5 and records E6 as stopped for insufficient qualified held-out
capacity. The preserved Tau3 remote run `20260812T040705Z-amax-ae0d3ec6b8e8` establishes only a
12-pair scripted **development** screen. It contributes zero qualified held-out pairs and cannot be
used as primary or secondary efficacy evidence.

The imported result and its exact claim boundary are frozen by
`configs/paper_2026/e6_remote_cpu_gate_20260812.result.lock.json`. Do not overwrite, delete, repair,
or relabel the original negative envelope.

## Branching rule

Before creating an E6 continuation branch:

1. commit the current paper branch, including all P0--E5 locks, E4/E5 analyses, the evaluator-audit
   preparation lock, the E6 capacity decision, and the imported remote-result record;
2. record that commit as the immutable paper baseline;
3. create the E6 branch from that baseline;
4. never modify or replace frozen P0--E5 outputs on the E6 branch;
5. write every repaired or new run into a new versioned output directory.

## Work still required on the E6 branch

### E6-A. Versioned infrastructure repair

- Add a pinned `cryptography` dependency to the isolated Tau3 CPU environment.
- Run repository tests in a fresh subprocess so the branch screen cannot pre-populate `sys.modules`
  and invalidate lazy-import tests.
- Add regression tests that reproduce both failures from the preserved envelope.
- Version the runner/config/requirements and document the repair as infrastructure-only.
- Produce a new remote run directory; do not reuse
  `20260812T040705Z-amax-ae0d3ec6b8e8`.
- Require the branch screen, schema validation, and the complete repository suite all to pass.

Passing E6-A still creates **zero held-out capacity** and authorizes no model run.

### E6-B. Prospective held-out qualification

- Start only from the 54 prospectively reserved Tau3 held-out tasks.
- Exclude development pairs, memory-source families, model-exposed families, and all targets used to
  tune an E6 rule or adapter.
- Qualify at least 30 independent tasks across at least three failure or recovery families.
- Use one generic failure-injection, recovery, and observable-success interface across domains.
- Preserve non-idempotent safety: unknown outcomes must verify or stop before retry.
- Keep task IDs, evaluator actions/outcomes, gold actions, scenario/family metadata, and prior model
  outputs outside method inputs.
- Freeze the qualified task manifest and all exclusions before reading any new model output.

If this gate fails, stop E6 and do not manufacture or relabel capacity.

### E6-C. Frozen external model protocol

Only after E6-B passes:

- freeze models, prompts, memory bank, No Memory/TF-IDF/LLM Judge/PROPER conditions, decoding,
  environment, endpoint, stopping rule, and multiplicity family;
- validate a small development-only smoke set and permanently exclude it from held-out results;
- run the complete condition matrix without selective regeneration or parse repair;
- report final task success, first recovery-action correctness, invalid/repeated calls,
  non-idempotent duplicate side effects, tool calls, tokens, latency, and the
  selection-to-behavior gap;
- retain intention-to-treat failures and report both model families separately.

### E6-D. Reliability and integration

- Perform blinded review under a rule frozen before model outputs.
- Hash-lock raw generation, environment traces, evaluation, statistics, and paper-facing tables.
- Merge E6 claims into the current manuscript only if all gates pass without altering P0--E5.
  Otherwise retain E6 as a separate follow-up project or limitation/future-work item.

## Current missing items at a glance

| Item | Current state | Required state |
|---|---:|---:|
| Remote CPU envelope | failed infrastructure checks | new versioned pass |
| Qualified development pairs | 12 | sufficient only for adapter development |
| Qualified held-out pairs | 0 | at least 30 |
| Qualified failure/recovery families | 0 held-out | at least 3 |
| External model protocol | not frozen | frozen after capacity gate |
| External model outputs | none authorized | full matrix after protocol freeze |
| External blind review/statistics | absent | complete and hash-locked |
