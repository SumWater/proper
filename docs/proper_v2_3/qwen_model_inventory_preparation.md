# Qwen model inventory preparation

This CPU-only stage prepares one remote read-only inventory of the known local
Qwen3-8B directory. It does not establish a model revision by assumption: the
remote result must enumerate and hash the actual directory contents before the
acquisition runtime can be considered for freezing.

The inventory includes every regular file, including hidden files, sorted by
POSIX relative path. It records each size and streaming SHA-256, the total
bytes and file count, and a canonical combined manifest SHA-256. The configured
root is an exact absolute path. Empty directories, symbolic links, and special
filesystem entries stop closed; no exclusion or filename-based shortcut is
allowed.

The remote entry verifies the exact project revision, a clean tracked
worktree, Python 3.11/3.12, and the closed read-only boundary before reading
model file bytes. It imports no model or tau library. It does not instantiate
a tokenizer or model, inspect generated output, execute a task, initialize a
GPU, or authorize branch capture. Both successful and failed inventories are
written to a unique run directory.

Local validation uses temporary toy directories only. Six scoped tests cover
sorting/completeness, deterministic manifests across chunk sizes, content
change sensitivity, streaming hashes, relative/empty-root rejection, and the
symlink stop when the host permits creating a symlink. They also exercise the
complete remote result envelope against the closed schema field set. The local
Windows host may report the symlink branch as one explicit skip; remote
inventory behavior is still stop-closed in source and configuration.

Passing preparation authorizes only the command in
`qwen_model_inventory_handoff.md`. After the remote result is synchronized
back, it must be schema-checked and frozen locally before any acquisition
runtime, model loading, tau task, real branch capture, or GPU use is considered.
