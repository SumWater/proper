# Confirmatory Transient Authorization v1: Preparation Record

The initial deterministic Linux preparation completed before any model was
loaded or any model output was read or generated. After the environment-lock
revision described below, the current payload was regenerated deterministically
without model execution; the formal runner must reconstruct it on Linux before
loading the model.

- valid released transient-authorization targets: 175
- frozen selector-changed primary pairs: 53
- unchanged descriptive targets: 122
- primary target tools: 7
- primary selected memories: 12
- planned per-target model calls: 228
- globally distinct prompt texts: 213

The saved 175-record payload reconstructs exactly from the frozen public-test
file, dev memory bank, capacity artifact, selector, and configuration. Its
canonical payload SHA256 is
`4af16c2bd75bbb3164c13bd90aee68786147885ed7bb61657defe939a337a0e1`.
The saved prepared-file SHA256 is
`1a8a72b9554ceceaaa041fde04dacabe1966aa31b80f5ca47bf70570022ba806`.

This record authorizes the single frozen GPU run. It does not alter the cohort,
prompt content, selector, conditions, model settings, endpoints, or inference
rules. The run must stop on any prepared-artifact or source-manifest mismatch.

Before model execution, installation of the repository's `jsonschema` and
`scikit-learn` test dependencies changed the pip-freeze artifact while leaving
the conda explicit lock and inference-core package versions unchanged. The
current pip environment is frozen under SHA256
`e215575984b1f02914e781348564fa8426adb717154bc91a5d39d8af6ec8cc8b`.
The prepared payload is deterministically regenerated for this environment
identity, and the formal runner reconstructs it again before loading the model.
