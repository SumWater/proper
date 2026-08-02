# Qwen model inventory result

The remote read-only inventory passed at project revision
`a740a864f8fe9fac2cdaec5374aa90cea3c6db95`. It recorded 15 regular files
totaling 16,397,461,266 bytes. The canonical content-manifest SHA-256 is
`f981a4a7978fd128d6efb18d93b8810d98434a8e69c9bd517ad7aa4e5c1b6a07`.
The returned result file SHA-256 is
`5717e0e22132b4392883e2b3f4896dfe77789ce856f47a42bf4023992eba8bc3`.

The inventory contains five numbered safetensors shards plus their index,
model and generation configurations, tokenizer files, vocabulary and merges,
and documentation metadata. This statement describes the observed file list;
it is not a post-hoc model-performance gate. The local freeze recomputes the
manifest from the ordered records, checks all per-file hashes syntactically,
verifies unique safe relative paths and byte totals, and confirms the exact
remote revision and frozen inventory-config hash.

Two earlier results at revision
`bcc758badf692932008824d0d0d05fcda865a177` are preserved separately. Both
stopped at the clean-worktree preflight, contain zero file records and zero
bytes, and have identical SHA-256
`4d369242f648fca11ec5b9f8a5df5e5572a80de9e873fd6aab7cb63d78195034`.
They are infrastructure-negative records, not model or method evidence.

No run imported or loaded the model, read generated output, executed a tau
task, used a GPU, or evaluated selector, lifecycle, continuation, completion,
safety, or cost. The exact model-directory content identity is now recorded,
but model compatibility and runtime behavior are not proven.

This freeze authorizes acquisition-runtime protocol design only. It does not
authorize acquisition-runtime execution, the 12 development tasks, public
branch capture, a model comparison runner, an external API, GPU use, or any
confirmatory claim.
