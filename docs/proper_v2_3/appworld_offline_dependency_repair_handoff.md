# AppWorld offline dependency repair handoff

The frozen dependency failure is preserved. This gate installs three exact,
hash-checked PyPI wheels into a new external target directory using
`--no-index --no-deps --only-binary=:all:`. It then probes exact versions and
invokes the unchanged aggregate-only inventory runner once.

No project environment is modified. The target must be absent and outside the
repository. Network access, source extraction, AppWorld tests/data, model use,
GPU use, and scientific claims remain closed. Any provisioning, import, or
inventory failure is persisted and stops the stage.
