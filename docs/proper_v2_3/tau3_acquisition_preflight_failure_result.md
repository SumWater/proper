# Tau3 acquisition preflight failure result

Remote run `20260803T064447Z-amax-8c2b38219291` stopped in preflight at
project revision `8c2b38219291406506606678b58069052348c3db`. Eleven of twelve
checks passed. The only failure was `tracked_worktree_clean=false`, caused by
four synchronized v2.3 README files that had not been included in the remote
commit.

The preflight SHA-256 is
`c2e4afae302bae7fecf035d1135de83bf344b5eb32c5b11291a0b74322ab078a`;
the result SHA-256 is
`221131fd27a99c3119e13f80b95b79adae2b81990b39448da95f99733bd54194`.
The local freeze-validation SHA-256 is
`f8616896b2efd4646718f09276f76333efc6261823035c3cda7469ef04d74fef`.

The result contains zero attempts, agent/user requests, prompt/completion
tokens, and native tool executions. It records `model_loaded=false`,
`model_outputs_read=false`, `task_executed=false`, and `gpu_used=false`.
Consequently this is an infrastructure preflight result, not selector,
lifecycle, continuation, completion, safety, cost, or model evidence.

All scientific inputs and execution prerequisites passed: project revision,
frozen hashes, tau revision and manifest, domain and task hashes, Qwen
inventory, both Python environments, worker dependencies, and CUDA device 0.
The method, prompt, budgets, model, task order, endpoints, exclusions, and stop
rules are unchanged.

After the four README files are committed and the tracked worktree is confirmed
empty, one invocation of the identical command is authorized. It uses a fresh
unique output directory. This consumes no model/attempt retry because the
failed run never crossed the preflight gate.
