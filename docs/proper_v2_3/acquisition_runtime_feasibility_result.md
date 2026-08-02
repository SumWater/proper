# Acquisition runtime feasibility result

The CPU-only audit stops before freezing or executing the real branch
acquisition runtime.

The existing Qwen3-8B path and text JSONL worker have prior local-agent
development evidence. However, that worker accepts only system, user, and
assistant text roles. It does not accept tau3 tool messages or emit native tau3
tool-call objects. The tau3 default user simulator instead calls the external
`gpt-4.1-2025-04-14` model through LiteLLM, but this project has no frozen
external endpoint, credential boundary, or network authorization for that
runtime.

Using Qwen3-8B as the user simulator is a plausible future implementation, not
an existing validated runtime. No local tau participant adapter, JSON output
contract, prompt templates, participant contract tests, or model-directory
manifest currently exists. The user-model revision is therefore also
unfrozen.

The audit preserves seven missing freezes and authorizes only two CPU-safe
implementation tasks:

1. implement and contract-test local Qwen tau agent/user participant adapters;
2. produce a remote read-only manifest of the local Qwen model directory.

No model loading, generation, task execution, branch capture, model runner,
external API, or GPU use is authorized. This is an infrastructure feasibility
result, not selector, lifecycle, continuation, completion, safety, cost, or
confirmatory evidence.
