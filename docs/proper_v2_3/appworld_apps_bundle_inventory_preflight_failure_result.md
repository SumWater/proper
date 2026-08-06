# AppWorld apps-bundle inventory preflight failure

Remote run `20260806T015829Z-amax-dd1cd0026747` stopped before decryption at
project revision `dd1cd002674740c2ff08fcbaa590ed41e65c0c4a`. The returned
result SHA-256 is
`4a57dfda39dd7db5fde99126a97439b8a21ae25095347b2a9a4dfbfdcec16bcd`.

The primary failure is environmental: `cryptography` is unavailable in the
selected remote Python environment. Consequently its version cannot be
validated and the inventory cannot start. Revision, frozen-input, clean-tree,
external-wheel, absolute-path, and zero-network/extraction/model checks all
passed.

The apps bundle was not decrypted. No tests bundle, protected plaintext,
source extraction, task/API content, model, or GPU was accessed. This is not a
candidate-capacity, selector, lifecycle, continuation, completion, or model
result, and it does not assess the PROPER method.

The failed result is retained rather than overwritten. A retry is not yet
authorized. The next permitted work is a separate offline or hash-pinned
dependency-provisioning protocol that preserves the same wheel, bundle,
reader, schema, limits, and scientific boundaries.
