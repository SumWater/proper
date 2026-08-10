# Historical Qwen output reuse audit

- Audit date: `2026-08-09`
- Repository HEAD: `44e5b11104e3d0e46933b22311527c22828ec1cd`
- Audit status: local artifacts verified; reuse remains conditional on paper prompt manifests

## Shared model identity

- Model: Qwen3-8B
- Model manifest: `configs/proper_v1/qwen3_8b_model.sha256`
- Manifest SHA-256: `aa3e07db476dac6f3af8ad14958cb6febee947243f4bc29d7f6c5eda5c92e4ba`
- Backend: Transformers
- Decoding: `do_sample=false`, `temperature=0.0`, `max_new_tokens=256`
- Thinking: disabled
- Recovery horizon: one post-failure decision

The historical runner applies a Qwen chat template to a fixed system message and the raw user prompt.
The paper cache must therefore check both raw prompt identity and rendered-message policy.

## Artifact table

| Stratum | Result artifact | SHA-256 | Records | Conditions | Distinct raw prompts | Local status |
|---|---|---|---:|---|---:|---|
| argument omission | `outputs/proper_v1/confirmatory_gate_v1/results.json` | `6e44ef0eba2bf7efeed7163d61a621d2a1a5385b6aa507f7ce0417222d2fceb8` | 189 | No Memory, TF-IDF, PROPER, matched applicable | 492 | full records present |
| transient authz | `outputs/proper_v1/confirmatory_transient_authz_v1/results.json` | `26fd9c062a3d462f7cefd164c3d9f7bc5460b06a2bd16cd66e5b177e1c0cd276` | 175 | TF-IDF, PROPER | 213 | full records present |
| timeout | `outputs/proper_v2/timeout_pair_v2/results.json` | `7278518e12dbe6c2c9805464678e24d82478f9270875377aa80cafbcdd2c91f9` | 177 | TF-IDF, PROPER | 198 | full records present; no post-run result lock |

All three result files contain per-record prompts, prompt hashes, raw model outputs, parsed decisions,
outcomes, observable-prefix identities, and condition identities. All reported parse-failure counts are
zero.

## Reuse decision by condition

| Stratum | No Memory | TF-IDF | Historical PROPER | Oracle/applicable control |
|---|---|---|---|---|
| argument omission | conditionally reusable | conditionally reusable | conditionally reusable | conditionally reusable as descriptive matched-applicable control |
| transient authz | must run | conditionally reusable | conditionally reusable | no historical output |
| timeout | must run | conditionally reusable | conditionally reusable | no historical output |

“Conditionally reusable” means that the new `prompt_manifest.json` reproduces the exact raw prompt
hash, Qwen model manifest, system message, chat-template policy, decoding, parser, and execution
semantics. It does not mean that aggregate counts may be copied into a new result table without a
record-level join.

Dense Retrieval, LLM Judge, PROPER-no-gate, and PROPER-no-contradiction are new conditions and have no
historical output unless they happen to produce a prompt whose full cache identity is exactly equal to
an existing condition.

## Audit caveats

1. The argument-omission runtime config was refactored after the completed result. The result records
   identify original config SHA-256
   `781f8305162840e6ce6e3ca43890255ace0bda4e3108997e2b62d92a085423f1`; reuse must rely on the locked
   result and prompt records, not assume the current runtime YAML is byte-identical.
2. The transient-authz result embeds original config SHA-256
   `e7f382e4c2bd70f9ace5695ff8b31becabeba5023777f1286071bc3a94751e00`.
3. The timeout output exists and is complete, but `configs/proper_v2/timeout_pair_v2.lock.json` remains a
   pre-output lock with `model_outputs_generated=false`. Treat timeout as previously observed historical
   evidence, not as a newly preregistered confirmation. The paper audit must preserve this provenance.
4. The local workspace contains `work/confirmatory_gate_v1_prepared.json`, but the transient-authz and
   timeout prepared manifests are not present locally. Their full result records are present, so
   prompt-level cache construction remains possible; preparation-file reproduction must be performed
   separately if required.

## P0 conclusion

The local workstation does not need model weights to reuse eligible Qwen outputs. A paper-level cache
builder can read the immutable historical result files, join by full identity, and emit provenance into
new `outputs/paper_2026/` artifacts. No historical file should be copied or overwritten.

