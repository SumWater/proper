# Compatibility audit findings

## Checkpoint 1: environment and remote identities

Evidence timestamp: 2026-07-21T08:13:49Z. Evidence is local under `work/` and intentionally ignored by Git.

### Passed

- WSL2 Ubuntu-compatible environment has Bash 5.1.16, Git 2.34.1, Python 3.10.6, curl 7.81.0, and GNU `sha256sum` 8.32.
- The project compiles under Python 3.10 and all four local recovery-contract tests pass.
- GitHub advertised default branch `master` at commit `b6ee3412f98d2058ee487e182a72b26c58046d51`.
- Hugging Face API advertised immutable dataset revision `98eb28718b0393e029088ce80604c48807216de4`.
- No task data, model, benchmark checkout, rollout, or GPU job was acquired/run.

### Version finding

The Hugging Face repository is a mixed-release container:

- root `manifest.json` and `v0_1_freeze.json` describe v0.1 with 5,000/800/1,000 tasks;
- current README declares `v0_2_large` with 6,000/900/1,200 tasks;
- `EXPORT_MANIFEST.json` points to the v0.2 data under `data/v0_2_large/` and its release metadata under `artifacts/v0_2_large/`.

Consequently, the root manifest must not be used to validate v0.2. The candidate v0.2 manifest is `artifacts/v0_2_large/manifest.json` at the frozen HF revision. The values in `observed_candidates` are discovery results, not an approved lock.

### Still unverified

- v0.2 manifest/freeze contents and checksums at the immutable revision;
- whether the candidate GitHub commit loads and evaluates v0.2 without silent conversion/defaults;
- upstream dependency compatibility under Python 3.10;
- deterministic replay, snapshot/fork support or deterministic prefix fallback;
- the exact agent-visible boundary and leakage of evaluator-only fields;
- recovery-contract and correct-stop evaluation against real benchmark traces;
- independence of the official task-success result from the added metric layer.

### Acquisition-script correction

The first source-acquisition attempt stopped safely. The original script cloned with `--no-checkout`; Git represented the intentionally empty work tree as staged deletion of every tracked file, so the dirty-tree guard rejected it. Inspection confirmed that the directory contained only `.git`, its origin was the expected repository, and HEAD was the expected candidate commit. The script now performs a normal checkout for new clones and repairs the prior empty state only when `.git` is the sole entry and every status record is an index deletion. Any real work-tree content or other modification still causes a hard stop.

### Decision

Status remains `UNVERIFIED_DO_NOT_RUN_EXPERIMENTS`. The next bounded step may acquire only the code checkout at the observed immutable commit plus small release metadata. Dataset task files remain out of scope until code and manifest inspection succeeds.

## Checkpoint 2: immutable source and static interface audit

The official code checkout is clean at commit `b6ee3412f98d2058ee487e182a72b26c58046d51` with tree `ce6663afa7f7df21e878bbde80764b77aeb80bd0`. The immutable v0.2 manifest has SHA-256 `dbc940b8ead00071b8287d301384091077158f4296fd330c36ba022b6fa93c0d` and declares a 1,249,342-byte dev split with SHA-256 `a5a2b49b28c66f01bdbac37966c00cca9c6a1027a6d4b5b3a8c1d1d359db27e3`.

Static findings:

- `Observation` contains only instruction, tool schemas, transcript, remaining budget, and last error at its top level. Task `fault_plan`, `gold_summary`, `success_criteria`, initial state, and seed are not copied directly into the initial observation.
- This top-level isolation is defeated after injection: `FaultEvent` contains `fault_type`, `severity`, and the complete fault `payload`; the environment attaches it to error/output details, records those details in the transcript, and passes both transcript and last error back to the agent. The v0.2 payload includes oracle-like fields such as `recoverability`, schema rename mappings, drift visibility, and required role. Runtime leakage testing is mandatory; compatibility is not passed.
- For schema drift, the environment records the transformed effective action rather than necessarily preserving the action returned by the agent. Behavior matching therefore requires an agent-boundary action recorder outside the official transcript.
- `snapshot()` returns only a deep copy of business state. It omits transcript, last error, step/tool/retry counters, fault-engine RNG state, and task identity, and there is no restore method. Failure-state snapshot branching is unsupported by the current interface.
- Deterministic reset/prefix replay appears plausible because reset reconstructs state, counters, seeded RNG, and the fault engine, but must be verified on the frozen v0.2 sample.
- Released v0.2 authorization plans use `on_nth_call: 1` and label their payload `transient_denial`; they do not natively instantiate the pilot's persistent-authorization-denial class. A locally declared persistent fault plan may be technically possible, but it must be reported as an audit extension rather than a native released-data condition.
- Returning `None` stops the official runner, but `EpisodeResult` has no structured stop reason. Correct Stop cannot be recovered from official artifacts alone; it requires an external agent wrapper and independent metric layer while leaving official task success unchanged.

The next runtime audit is bounded to the checksummed 1.25 MB dev split, pinned CPU-only Python dependencies, upstream tests, three-run replay, one-step prefix replay, and observation/action-boundary instrumentation.

### WSL runtime prerequisite

The first runtime attempt successfully downloaded and verified the 1,249,342-byte dev split, then stopped before dependency installation because Ubuntu Python 3.10 lacked `ensurepip`/the `python3.10-venv` system package. This is an environment prerequisite failure, not a ToolMisuseBench compatibility result. The script now checks `ensurepip` explicitly and uses a fresh versioned audit-environment path so the incomplete first environment is never reused.

The prerequisite installation subsequently completed successfully. Ubuntu upgraded Python 3.10 from 3.10.6 to the Jammy security-update build 3.10.12 and installed `python3.10-venv`, `python3-pip-whl`, and `python3-setuptools-whl`. The runtime audit must freeze the resulting isolated environment before its result is considered reproducible.

## Checkpoint 3: declared Python compatibility failure

The isolated dependency environment was created and frozen successfully (initial freeze SHA-256 `f7c34046732d15713da9130f1d55315ea93a228277ec0399d84b2eac0de3a4ab`). Upstream test collection then failed in five modules before any tests ran:

- upstream `pyproject.toml` declares `requires-python = ">=3.10"`;
- `toolmisusebench/version2/release_runner.py` imports `UTC` from `datetime`;
- `datetime.UTC` is unavailable in Python 3.10, producing an import error through the CLI module;
- the affected collections include agent loader, baselines, CLI smoke, experiment pipeline, and v0.2 release runner tests.

This is a confirmed code/environment compatibility defect at the frozen commit, not a failure of the pilot's metric code. The official checkout remains unmodified. The audit status stays `UNVERIFIED_DO_NOT_RUN_EXPERIMENTS`; a future approved lock must either require Python 3.11+ or identify an upstream commit that makes the declared Python 3.10 support true. Core environment tests that do not import the release runner can still be executed under 3.10 to assess replay and leakage independently.

A non-frozen Windows cross-check under Python 3.12.7, Pydantic 2.8.2, and pytest 7.4.4 collected the full suite: 38 tests passed and one v0.2 release-runner test failed when `os.replace` received `WinError 5` in the sandbox temporary directory. This is not accepted as a Linux compatibility result because the dependencies differ from the audit lock and the remaining failure is platform/permission sensitive. It does, however, support the narrower diagnosis that the five WSL collection errors share the Python 3.10 `datetime.UTC` root cause rather than representing five independent benchmark defects.

An audit-only Python 3.10 shim may temporarily define `datetime.UTC = datetime.timezone.utc` before test collection. Its sole purpose is to test whether further Linux failures exist behind the incorrect declared Python floor; it must not be used for experiments or treated as an upstream-compatible environment.

## Final checkpoint: conditional compatibility pass

The audit-only UTC shim allowed all 39 upstream tests to pass on WSL, isolating the declared Python-floor defect. The external adapter gate then passed all 900 dev tasks on Windows and WSL with the same aggregate trace SHA-256 `571638c81e9ab859ee6c3716b1bc73144ccfb08a11ee7629650110a09fbc5271`: zero sanitized replay failures, zero remaining injection leaks, and zero differences in official episode results. It detected 153 Agent-boundary versus official-transcript action mismatches, matching the 153 schema-drift tasks.

The persistent-authz extension/Correct Stop gate also passed on both platforms. It confirmed that released authz is transient, the explicitly labeled extension is persistently denying and deterministically replayable, structured stopping is recovery-valid, repeated calls violate the safety invariant, and independent evaluation leaves official Task Success unchanged.

The final decision is `PASS WITH ADAPTER AND DETERMINISTIC PREFIX REPLAY`, subject to every condition in `compatibility_decision.md` and the version lock. This supersedes earlier `UNVERIFIED` checkpoint statuses for the bounded pilot only.
