# PROPER paper 2026 configurations

This directory contains only the new paper protocol and execution locks. Historical configurations
under `configs/proper_v1/`, `configs/proper_v2/`, and `configs/proper_v2_3/` are read-only ancestry.

Current artifact:

- `p0_local_sources.sha256`: local P0 documents, inventory runner, historical result inputs, and Qwen
  model-identity manifest required for the remote handoff.
- `bge_large_en_v1_5.sha256`: frozen six-file manifest for the Dense Retrieval encoder candidate.
- `dense_retrieval_v0_1.yaml`: frozen BGE direct-Transformers encoding and selection policy; remote
  smoke passed.
- `dense_retrieval_v0_1.result.lock.json`: accepted BGE model, runner, environment, and smoke-result
  identities.
- `llm_judge_v0_1.yaml`: frozen Qwen3-8B applicability reranker prompt, TF-IDF Top-10 candidate
  policy, strict parser, and deterministic Rank-1 fallback; remote exact-prompt smoke passed.
- `llm_judge_v0_1.result.lock.json`: accepted Judge model, prompt source, parser policy, runner, and
  exact-prompt smoke identities.
- `p0_protocol_v1_0.lock.json`: closing P0 lock that authorizes E1 offline selection only.
- `environment_selection_v0_1.yaml`: selected existing GPU environment and pre-smoke execution policy.
- `dual_agent_runtime_v0_1.lock.json`: passed common smoke and frozen execution identity for Qwen and
  Mistral.
- `model_b_candidate_v0_1.yaml`: authorized cross-family second model; the remote storage gate passed.
- `model_b_manifest_v0_1.lock.json`: pinned Mistral identity and passed remote BF16 smoke evidence.
- `selector_policy_v0_1.yaml`: frozen shared-selector policy and two single-component ablations.
- `selector_capacity_audit_v0_1.yaml`: frozen-input, model-free three-stratum capacity audit.
- `selector_capacity_audit_v0_1.result.lock.json`: locked 541-target capacity result and selector
  source identities.
- `statistics_v0_1.yaml`: prespecified paired-binary effects, bootstrap procedure, and Holm families.

`docs/paper_2026/protocol.md` is `1.0-frozen`. E1 offline selection is authorized; formal agent
generation remains blocked until E1 freezes its changed-target union and stage-specific prompt lock.

Model B download authorization was conditional on the read-only storage gate recorded in
`outputs/paper_2026/p0_remote_storage.json`; that gate passed before the download command was issued.

The remote environment lock and both model identities are accepted. Mistral and Qwen passed the same
smoke implemented by `scripts/paper_2026/smoke_agent_model.py`; the dual-agent runtime is frozen. The
BGE Dense encoder also passed its direct-Transformers smoke and is frozen for E1 selection.

The non-model selector-capacity preflight is implemented by
`scripts/paper_2026/check_capacity_audit_inputs.py`. Its first run verified the 189/175/177 historical
target contexts and 100-source memory-bank context, and identified only the frozen development and
public-test JSONL files as missing local reconstruction inputs.
