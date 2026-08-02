# Local tau participant adapter contract

This stage closes the participant-interface gaps identified by the acquisition
runtime feasibility audit without loading a model or executing a tau task.

The adapter maps complete participant-visible history to the existing local
Qwen JSONL worker's `system`, `user`, and `assistant` text roles. Public tool
calls and results are canonical JSON text records because the worker has no
native tool role. The agent receives only the public domain policy, public tool
contracts, and public history. The user simulator receives the public
simulation guidelines, its private scenario, and the same public history with
half-duplex roles reversed. Private user scenarios are never sent to the
agent, and domain policy is never sent to the user simulator.

Both participant outputs must be exactly one JSON object. An agent output is
exclusively a non-empty message or one named public tool call. Tool names,
required and additional arguments, JSON types, nested objects/arrays, and
enums are checked against the public tool schema before a native action can be
considered. A user output is exclusively one non-empty message. Public
histories for both participants reject evaluator metadata such as task IDs,
gold actions, recoverability, and evaluator outcomes.

Generation parameters are frozen at seed `20260730`, `max_new_tokens=256`,
greedy decoding, temperature zero, and thinking disabled. These values are a
future runtime contract only: validation does not import a model library, load
model files, read model outputs, run a tau task, or use a GPU.

The CPU validation runs eight scoped tests and hashes the prompt config,
decision schema, adapter source, and tests. Passing authorizes only a remote
read-only inventory of the known Qwen model directory. Acquisition-runtime
freezing, real branch capture, model execution, model-runner implementation,
external API use, and GPU use remain closed until that inventory is returned
and frozen locally.
