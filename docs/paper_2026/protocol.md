# PROPER paper 2026 protocol

- Protocol version: `1.0-frozen`
- Date opened: `2026-08-09`
- Date frozen: `2026-08-10`
- Status: `FROZEN_FOR_E1_OFFLINE_SELECTION`
- Formal offline selector runs authorized: `true`, E1 only
- Formal agent generation authorized: `false`
- Historical model outputs read during design: `true`

This is a prospective protocol for the new comparison matrix, not a claim that the entire paper is
preregistered. The Qwen3-8B argument-omission, transient-authorization, and timeout outputs have
already been observed. They are historical evidence and may be reused only by exact prompt and model
identity. New baselines, a second model family, and ablations must be frozen before their formal
outputs are generated.

## 1. Scope and claim

The paper studies conservative failure-memory selection for a tool-using LLM agent after an
observable execution failure. The intended claim is limited to the evaluated models, benchmark,
failure strata, memory bank, and one-step recovery setting.

The paper does not claim that inapplicable memories are universally harmful, that selection changes
always alter behavior, or that the method generalizes to every agent architecture. PROPER v2.3's
execution ledger is outside the primary contribution.

## 2. Paper-level PROPER contract

Before E1 starts, the paper implementation must expose one shared interface:

```text
ObservableFailureState + RankedMemoryCandidates + FrozenPolicyTaxonomy
    -> keep_rank1 | select(candidate_id) | abstain
```

Allowed inputs are the user task, public tool schemas, failed action, public error/return, observable
history, candidate memory text and provenance available at retrieval time, and deterministic features
derived from those inputs.

Forbidden inputs are benchmark scenario names, hidden fault plans, recoverability labels, gold
actions, evaluator outcomes, prior model outcomes, or branches keyed to argument omission,
authorization, or timeout dataset names.

Failure-type differences must be represented through observable failure evidence and a frozen policy
taxonomy. The existing scenario-specific v1/v2 implementations are evidence ancestors; they are not
automatically the final shared paper implementation.

Frozen implementation `proper_paper_2026_v0_1_frozen` exposes this interface under
`src/failure_memory/paper_2026/`. It preserves Rank-1 on abstention and separates the conservative
replacement gate from contradiction checking so the two planned ablations remove exactly one component.
Its offline three-stratum capacity audit passed before new formal model outputs: full PROPER changed
205 of 541 TF-IDF identities, while no-gate and no-contradiction differed from full PROPER on 95 and
36 prompt identities respectively.

## 3. Research questions and endpoints

- RQ1: Does PROPER improve paired Recovery Validity over TF-IDF Rank-1?
- RQ2: Is PROPER competitive with Dense Retrieval and an LLM applicability judge?
- RQ3: Are results directionally consistent across two model families and three failure strata?
- RQ4: What is contributed by the conservative gate and contradiction check?
- RQ5: What coverage, erroneous-selection, negative-transfer, safety, and cost trade-offs result?
- RQ6: Conditional on external target capacity, do selection changes alter end-to-end behavior?

The primary endpoint is paired binary Recovery Validity. Secondary endpoints are task completion,
action/tool change, safety violation, repeated invalid calls, parse failure, token count, latency,
model-request count, selection coverage, and erroneous-selection rate.

The primary comparison is PROPER versus TF-IDF. PROPER versus Dense and PROPER versus LLM Judge
are multiplicity-corrected key secondary comparisons. Oracle is descriptive only.

## 4. Data and populations

Frozen historical valid targets:

- argument omission: 189;
- released transient authorization: 175;
- timeout: 177.

The paper must preserve source/target isolation and the existing frozen 100-source development memory
bank unless a new memory bank is defined and locked before any new formal output. Existing public-test
inputs are model-output holdout only, not unseen-input holdout.

The main new behavioral population is the union of targets where at least one non-oracle memory
selector in `{Dense, LLM Judge, PROPER, PROPER-no-gate, PROPER-no-contradiction}` selects a different
memory identity than TF-IDF. No Memory and Oracle do not define this union. The union is frozen before
formal agent generation. All-valid-target results are secondary and use prompt-hash caching.

Historical changed-pair populations remain separately reportable for exact reproduction of previous
results; they are not silently merged with the new union.

## 5. Conditions

Main conditions:

1. No Memory;
2. TF-IDF Rank-1;
3. Dense Retrieval Rank-1;
4. LLM Applicability Judge/Reranker;
5. PROPER;
6. Applicable Oracle, descriptive selection upper bound only.

Ablations:

- PROPER-no-gate;
- PROPER-no-contradiction.

The Dense encoder and its execution policy are frozen in
`configs/paper_2026/dense_retrieval_v0_1.yaml`. The LLM Judge design is frozen in
`configs/paper_2026/llm_judge_v0_1.yaml` pending a development-only exact-prompt smoke. It uses the
fixed Qwen3-8B judge for both agent-model families to jointly rerank the source-blind TF-IDF Top-10,
exposes only anonymous candidate IDs and natural memory text, disables thinking and sampling, and
falls back to TF-IDF Rank-1 after any strict-JSON parse failure. No format-repair call is made. The
protocol must advance to `1.0-frozen` before formal outputs.

## 6. Models and generation

Agent model A is the frozen Qwen3-8B represented by
`configs/proper_v1/qwen3_8b_model.sha256` with manifest SHA-256
`aa3e07db476dac6f3af8ad14958cb6febee947243f4bc29d7f6c5eda5c92e4ba`.

The experiment-machine operational path reported on 2026-08-09 is
`/home/amax/PycharmProjects/AINegoProject/src/Models/LLM/Qwen3-8B`. This absolute path is not part of
the scientific model identity; the file manifest is authoritative and must pass before reuse or
inference.

Agent model B is the non-Qwen `mistralai/Mistral-7B-Instruct-v0.3` at immutable revision
`c170c708c41dac9275d15a8fff4eca08d52bab71`. Its returned 11-file, 14,498,803,728-byte manifest has
passed local structural and payload-hash verification and is locked by
`configs/paper_2026/model_b_manifest_v0_1.lock.json`. Remote verification checked all 11 files with
zero failures, and the model passed single-GPU BF16 strict-JSON smoke under Torch 2.12.0 and
Transformers 5.8.1. Peak allocated CUDA memory was 13,851.5 MiB. It was
chosen before new formal outcomes using these criteria, in order:

1. distinct model family;
2. stable local Transformers inference and a valid chat template;
3. fits available GPU memory without changing task semantics;
4. redistributable model identity and immutable file/revision manifest;
5. no model choice based on PROPER's observed effect.

No model is downloaded or run on the local workstation. The experiment machine is the only model
execution environment.

Historical Qwen settings were deterministic decoding, thinking disabled, `max_new_tokens=256`, and
one post-failure decision. The new matrix will retain deterministic decoding unless the selected model
cannot support it. Model-specific chat templates are permitted, but the system/user message semantics
must remain fixed and rendered prompt hashes must be recorded.

Both Qwen3-8B and Mistral-7B-Instruct-v0.3 passed the same single-visible-GPU BF16 strict-JSON smoke
under the frozen `failure-memory-pilot` environment. Their 15 and 11 manifest files respectively
verified with zero failures. The combined execution identity is locked in
`configs/paper_2026/dual_agent_runtime_v0_1.lock.json`.

## 7. Historical-output reuse rule

A historical output may be reused only if all of the following match:

- exact raw user prompt SHA-256;
- exact system message and chat-template rendering policy;
- exact model file manifest;
- decoding configuration;
- parser and one-step execution semantics;
- instance identity and observable prefix hash.

Reuse is condition-level, never result-level imputation. If any identity is missing or mismatched, the
condition is rerun under `outputs/paper_2026/`; the historical file remains untouched.

The current audit is recorded in `historical_reuse_audit.md`.

## 8. Statistical analysis

For paired binary outcomes, report positive/negative discordant counts, paired risk difference,
paired-instance percentile bootstrap 95% confidence intervals with 10,000 replicates, and exact
two-sided McNemar binomial tests. Seeds are deterministically derived from the frozen base seed and
analysis-cell identity.

Apply Holm correction separately to three prespecified families: PROPER versus TF-IDF across the six
model-by-failure-stratum cells; PROPER versus Dense and PROPER versus LLM Judge across those cells;
and PROPER versus each of the two ablations across those cells. Oracle and subgroup analyses are
descriptive unless a separate family is declared before formal outputs. The executable candidate and
full definitions are locked in `configs/paper_2026/statistics_v0_1.yaml` and
`docs/paper_2026/statistics_design_v0_1.md`.

Report results by model, failure stratum, target tool, and selected memory. Perform leave-one-tool-out
and leave-one-memory-out analysis, including explicit removal of `get_doc` and the maximum-contributing
memory. Zero and negative results remain in all tables.

No threshold, method rule, exclusion, primary population, or endpoint may be changed after new formal
outputs are inspected. Implementation bugs must be versioned and fixed uniformly across conditions.

## 9. Evaluation reliability

The evaluator must be deterministic where possible and blind to method names. Audit every discordant
pair and a stratified 20% sample of non-discordant pairs. A second annotator is preferred; if available,
report agreement and Cohen's kappa. Otherwise report single-reviewer validation as a limitation.

## 10. Remote execution boundary

The local workstation performs source audit, protocol writing, selector preparation, manifest
generation where dependencies allow, and result analysis. The experiment machine performs model
inventory, smoke tests, and all formal model inference.

The first remote action is inventory only. It must not download a model, run agent inference, or inspect
new method outcomes. Commands are documented in `remote_execution_handoff.md`.

The first inventory was returned as `outputs/paper_2026/p0_remote_inventory.json` with SHA-256
`5575046e5306f6979512cb5e9e337ac6fc5d90f6296a0f6b7965ae6dce019758`. It verified all 15 Qwen
manifest files and found two RTX 5880 Ada GPUs with 49,140 MiB each. It found no non-Qwen 7B/8B
instruction model. It did find a cached `BAAI/bge-large-en-v1.5` snapshot at revision
`d4aa6901d3a41ba39fb536a557fa166f842b0e09`. Direct-Transformers loading, six-file manifest
verification, first-token pooling, normalization, and a development-only relevance check subsequently
passed and are locked in `configs/paper_2026/dense_retrieval_v0_1.result.lock.json`.

The same inventory reported no installed-distribution metadata for Torch, Accelerate, BitsAndBytes,
SentenceTransformers, or scikit-learn in the active `proper-toolsandbox` environment, while
Transformers was 4.41.2. A second import-level diagnostic is required before the execution environment
or model B is frozen.

The second inventory confirmed those import failures and froze the BGE snapshot identity through
`configs/paper_2026/bge_large_en_v1_5.sha256`. Existing Conda environments must now be probed before
the project creates or mutates an environment. The active `proper-toolsandbox` environment is not
authorized for model execution in its current state.

The Conda probe selected the existing `failure-memory-pilot` environment. Its Python, Torch,
Transformers, Accelerate, and scikit-learn versions exactly match the historical environment lock.
The environment will not be mutated. It will use full BF16 inference and a direct Transformers BGE
implementation, so BitsAndBytes and SentenceTransformers are not required. Formal use remains blocked
until model smoke evidence is captured. The current full environment lock was captured as
`outputs/paper_2026/p0_environment_lock.json` with SHA-256
`fb943ddec5a962883c0e70cd1b863ad8c5547a0847107a76a175b53174a02443`. Its 94-entry Conda explicit
digest exactly matches the historical formal lock, and its 56 pip package entries match the historical
set. No environment mutation is required.

## 11. Post-P0 planned items

- exact new union size and planned agent-call count, to be produced and frozen by E1;
- external E6 benchmark capacity decision;
- second-annotator availability.

P0 is frozen. E1 offline Dense, LLM Judge, Oracle, PROPER, and ablation selection outputs are
authorized. New formal agent outputs remain unauthorized until E1 freezes the changed-target union,
the exact agent-call count, and the stage prompt manifest.
